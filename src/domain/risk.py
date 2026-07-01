"""Riesgo de umbral: margen de error de la mezcla y probabilidad de cobro.

Feature 2 del change-order. La refinería deduce un umbral por metal (7 g/t Au,
100 g/t Ag, 18 g/t Pd, 3 puntos % Cu): debajo de eso ese metal **no paga**. Como
la ley de la mezcla tiene incertidumbre (σ), el motor estima la **probabilidad de
superar el umbral y cobrar**, y avisa cuando un lote se sienta peligrosamente
pegado a un umbral con un metal ruidoso.

    grade_blend(m) = Σ f_i · grade_i(m)              # f_i = fracción de peso seco
    sigma_blend(m) = sqrt( Σ_grupos (Σ_{i∈g} f_i·σ_i)² )
    margin = grade_blend − umbral
    z      = margin / sigma_blend
    P_cobro = Φ(z) / Φ(grade/σ)                      # normal truncada en 0

Propagación por **grupos de correlación**: las pilas de un mismo bloque colineal
(solo viajaron juntas) comparten la incertidumbre de su ley → dentro del grupo
la σ suma lineal; entre grupos, en cuadratura. Y la probabilidad de cobro usa la
normal **truncada en 0** (una ley no puede ser negativa), que corrige el sesgo
pesimista cuando σ es grande relativa a la ley.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Iterable

from .models import PRECIOUS_METALS, ContractTerms
from .valuation import BlendComponent

# Margen mínimo sobre el umbral, en sigmas (configurable). 1.5 ≈ 93% de cobro.
DEFAULT_Z_MIN = 1.5
DEFAULT_K_SAFE = 1.0


def norm_cdf(z: float) -> float:
    """Φ(z): probabilidad de que una normal estándar sea ≤ z."""
    return 0.5 * (1.0 + math.erf(z / math.sqrt(2.0)))


def _threshold(metal: str, terms: ContractTerms) -> float:
    """Umbral de deducción del metal (debajo de esto no paga)."""
    if metal == "CU":
        return terms.cu_deduction
    return terms.rule(metal).deduction


@dataclass
class MetalRisk:
    """Riesgo de umbral de un metal en la mezcla."""

    metal: str
    grade: float          # ley de la mezcla
    sigma: float          # σ propagada de la mezcla
    threshold: float      # umbral de deducción
    margin: float         # grade − threshold
    z: float              # margin / sigma
    p_cobro: float        # Φ(z), probabilidad de superar el umbral y cobrar
    counts_value: bool    # si el metal aporta valor real al lote (grade > umbral)

    def safe(self, z_min: float = DEFAULT_Z_MIN) -> bool:
        """¿El cobro de este metal es seguro (z ≥ z_min)?"""
        return self.z >= z_min

    @property
    def grade_safe(self) -> float:
        """Ley conservadora (grade − k·σ, nunca por debajo del umbral)."""
        return grade_safe(self.grade, self.sigma, self.threshold)


def grade_safe(grade: float, sigma: float, threshold: float,
               k: float = DEFAULT_K_SAFE) -> float:
    """Ley conservadora para valorizar sin sobre-prometer: max(umbral, grade − k·σ)."""
    return max(threshold, grade - k * sigma)


def blend_threshold_risk(
    components: Iterable[BlendComponent],
    terms: ContractTerms,
) -> dict[str, MetalRisk]:
    """Riesgo de umbral por metal precioso de una mezcla (propaga σ)."""
    comps = list(components)
    dmt = sum(c.dry_weight_kg for c in comps)
    out: dict[str, MetalRisk] = {}
    if dmt <= 0:
        return out

    # Grupos de correlación: las pilas de un mismo bloque colineal comparten la
    # incertidumbre de su ley → dentro del grupo la σ suma LINEAL (correlación
    # total); entre grupos independientes, en cuadratura. Tratarlas como
    # independientes subestimaría la σ de la mezcla y volvería optimista la
    # probabilidad de cobro.
    groups: dict[object, list] = {}
    for c in comps:
        key = c.item.grade_block if c.item.grade_block else ("__solo__", c.item.code)
        groups.setdefault(key, []).append(c)

    for m in PRECIOUS_METALS:
        rule = terms.rule(m)
        if not rule.paid:
            continue
        grade = sum(c.item.grade(m) * c.dry_weight_kg for c in comps) / dmt
        var = sum(
            (sum((c.dry_weight_kg / dmt) * c.item.sigma(m) for c in grp)) ** 2
            for grp in groups.values()
        )
        sigma = math.sqrt(var)
        T = _threshold(m, terms)
        margin = grade - T
        if sigma > 0:
            z = margin / sigma
            # Normal TRUNCADA en 0: una ley no puede ser negativa. Con σ grande
            # relativa a la ley, la normal sin truncar reparte probabilidad en
            # valores imposibles (<0) y subestima la probabilidad de cobro.
            #   P(X > T | X ≥ 0) = Φ((g−T)/σ) / Φ(g/σ)
            p = min(1.0, norm_cdf(z) / max(norm_cdf(grade / sigma), 1e-12))
        else:  # sin incertidumbre conocida: determinístico
            z = math.inf if margin >= 0 else -math.inf
            p = 1.0 if margin >= 0 else 0.0
        out[m] = MetalRisk(
            metal=m, grade=grade, sigma=sigma, threshold=T,
            margin=margin, z=z, p_cobro=p, counts_value=grade > T,
        )
    return out
