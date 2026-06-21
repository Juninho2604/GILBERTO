"""Completar el contenedor: qué comprar para que el sobrante no pague $0.

El problema central del negocio: cuando lo que queda en depósito se envía tal
cual, suele estar dominado por pilas de bajo grado (p. ej. Bajo Grado Marrón).
La ley de la mezcla de algún metal cae por debajo del umbral de la refinería y
**ese metal pasa a pagar $0** — material perdido. La solución es **mezclar** el
sobrante con una pila rica para levantar la ley del lote por encima del umbral.

Este módulo, dado el sobrante y un catálogo de pilas que se pueden conseguir,
calcula:

- qué metales del sobrante están **bajo el umbral** (paga $0) o **frágiles**
  (apenas encima, con baja probabilidad de cobro);
- qué **pila comprar** (la que rescata todos los metales en riesgo con el menor
  peso agregado) y **cuántos kg**;
- el **% aprovechado** del sobrante antes y después de completar.

Matemática del refuerzo (ley de mezcla = promedio ponderado por peso seco):

    g_new = (g_L·D_L + g_R·d_R) / (D_L + d_R)  ≥  T_obj
    ⇒  d_R ≥ D_L·(T_obj − g_L) / (g_R − T_obj)        (requiere g_R > T_obj)

donde ``D_L`` es el peso seco del sobrante, ``g_L`` su ley, ``g_R`` la ley de la
pila a comprar y ``T_obj = umbral·(1 + margen)`` el objetivo con margen de
seguridad.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from math import inf
from typing import Optional, Sequence

from domain.models import ContractTerms, InventoryItem, MetalPrices
from domain.risk import blend_threshold_risk, norm_cdf
from domain.valuation import BlendComponent, value_blend

# Margen de seguridad sobre el umbral (20%): no basta con rozar el umbral, se
# busca quedar holgadamente por encima para cobrar con confianza.
DEFAULT_MARGIN = 0.20
# z mínimo para no considerar "frágil" un metal que ya supera el umbral.
DEFAULT_Z_MIN = 1.5
# Descuento de la ley de la pila a comprar por su margen de error (conservador):
# no recomendar comprar apostando a una ley ruidosa.
DEFAULT_K_SAFE = 1.0
_TIER_UNRELIABLE = "NOT_DETERMINED"


def _safe_grade(it: InventoryItem, metal: str, k_safe: float) -> float:
    """Ley conservadora de la pila a comprar: ``max(0, grade − k·σ)``."""
    g = it.grade(metal)
    if k_safe <= 0:
        return g
    return max(0.0, g - k_safe * it.sigma(metal))


def _eligible_booster(it: InventoryItem, metal: str) -> bool:
    """¿Sirve esta pila para reforzar ``metal``? Exige ley **confiable**.

    No se recomienda comprar contra una ley sin determinar (un número fantasma):
    aunque parezca riquísima, su incertidumbre la vuelve inservible como refuerzo.
    """
    return it.tier(metal) != _TIER_UNRELIABLE


@dataclass
class MetalGap:
    """Un metal del sobrante en riesgo (bajo umbral o frágil) y cómo rescatarlo."""

    metal: str
    grade: float           # ley actual de la mezcla sobrante
    threshold: float       # umbral de deducción
    target: float          # umbral·(1+margen): objetivo con holgura
    p_cobro: float         # probabilidad de cobro actual
    below: bool            # cae bajo el umbral hoy → paga $0
    fragile: bool          # supera el umbral pero con baja probabilidad de cobro
    booster_code: Optional[str]  # pila recomendada para levantarlo
    booster_grade: float         # ley (confiable) de esa pila en este metal
    booster_tier: str            # confianza de esa ley (MEASURED/ESTIMATED)
    add_kg: float          # kg (WMT) de esa pila para despejar SOLO este metal
    fixable: bool          # el catálogo tiene una pila confiable capaz de rescatarlo


@dataclass
class CompletionPlan:
    """Plan para completar el contenedor: diagnóstico + qué comprar."""

    leftover_kg: float
    leftover_util_pct: float       # % aprovechado si se envía el sobrante tal cual
    gaps: list[MetalGap] = field(default_factory=list)
    safe: bool = True              # el sobrante ya cobra todo: no hace falta comprar
    booster_code: Optional[str] = None   # pila primaria a comprar
    booster_grade_au: float = 0.0
    booster_tier: str = ""         # confianza de la ley de la pila primaria
    recommend_kg: float = 0.0      # kg (WMT) a comprar (rescata todos los metales)
    after_util_pct: float = 0.0    # % aprovechado tras agregar recommend_kg
    unfixable: list[str] = field(default_factory=list)  # metales sin pila capaz


def _eligible_metals(risk: dict, z_min: float) -> list[str]:
    """Metales bajo umbral o frágiles (apenas encima con baja prob. de cobro)."""
    out = []
    for m, r in risk.items():
        below = not r.counts_value          # grade ≤ umbral → paga $0
        fragile = r.counts_value and r.z < z_min
        if below or fragile:
            out.append(m)
    return out


def _kg_to_lift(dmt: float, g_l: float, g_r: float, target: float,
                moisture_r: float) -> float:
    """kg (WMT) de una pila de ley ``g_r`` para subir la mezcla a ``target``."""
    if g_l >= target:
        return 0.0
    if g_r <= target:
        return inf                          # la pila no alcanza para superar el objetivo
    dry = dmt * (target - g_l) / (g_r - target)
    return dry / max(1e-6, 1.0 - moisture_r)


def analyze_completion(
    leftover: Sequence[InventoryItem],
    catalog: Sequence[InventoryItem],
    prices: MetalPrices,
    terms: ContractTerms,
    *,
    margin: float = DEFAULT_MARGIN,
    z_min: float = DEFAULT_Z_MIN,
    k_safe: float = DEFAULT_K_SAFE,
) -> CompletionPlan:
    """Diagnostica el sobrante y recomienda qué comprar para completarlo.

    ``leftover``: pilas que quedan (``quantity_kg`` = kg del sobrante).
    ``catalog``: pilas que se podrían comprar (con ley **confiable**). Se elige la
    que rescata todos los metales en riesgo con el **menor peso agregado**, usando
    la ley conservadora (``grade − k·σ``) para no apostar a estimaciones ruidosas.
    """
    comps = [BlendComponent(it, it.quantity_kg) for it in leftover if it.quantity_kg > 0]
    leftover_kg = sum(c.weight_kg for c in comps)
    if not comps:
        return CompletionPlan(leftover_kg=0.0, leftover_util_pct=0.0, safe=True)

    base = value_blend(comps, prices, terms)
    risk = blend_threshold_risk(comps, terms)
    dmt = sum(c.dry_weight_kg for c in comps)

    metals = _eligible_metals(risk, z_min)
    if not metals:
        return CompletionPlan(
            leftover_kg=leftover_kg,
            leftover_util_pct=base.metal_utilization_pct,
            safe=True,
        )

    cand = [it for it in catalog if it.quantity_kg >= 0]  # catálogo (puede repetir pila)

    # Detalle por metal: mejor pila individual (confiable) y kg para despejarlo.
    gaps: list[MetalGap] = []
    for m in metals:
        r = risk[m]
        target = r.threshold * (1.0 + margin)
        best_code, best_grade, best_tier, best_kg = None, 0.0, "", inf
        for it in cand:
            if not _eligible_booster(it, m):
                continue
            gr = _safe_grade(it, m, k_safe)
            if gr <= target:
                continue
            kg = _kg_to_lift(dmt, r.grade, gr, target, it.moisture)
            if kg < best_kg:
                best_code, best_grade, best_tier, best_kg = it.code, gr, it.tier(m), kg
        gaps.append(MetalGap(
            metal=m, grade=r.grade, threshold=r.threshold, target=target,
            p_cobro=r.p_cobro, below=not r.counts_value,
            fragile=r.counts_value and r.z < z_min,
            booster_code=best_code, booster_grade=best_grade, booster_tier=best_tier,
            add_kg=(0.0 if best_kg is inf else best_kg),
            fixable=best_code is not None,
        ))

    # Solo los metales BAJO el umbral hacen falta rescatar sí o sí (pagan $0). Los
    # frágiles que ya superan el umbral son una advertencia, no una compra obligada.
    must_fix = [g.metal for g in gaps if g.below]
    unfixable = [g.metal for g in gaps if g.below and not g.fixable]

    # Pila primaria: la que rescata TODOS los metales bajo umbral con menos peso.
    best_pile, best_total_kg = None, inf
    for it in cand:
        need = 0.0
        ok = bool(must_fix)
        for m in must_fix:
            target = risk[m].threshold * (1.0 + margin)
            if not _eligible_booster(it, m):
                ok = False
                break
            gr = _safe_grade(it, m, k_safe)
            if risk[m].grade >= target:
                continue
            if gr <= target:
                ok = False
                break
            need = max(need, _kg_to_lift(dmt, risk[m].grade, gr, target, it.moisture))
        if ok and need < best_total_kg:
            best_pile, best_total_kg = it, need

    plan = CompletionPlan(
        leftover_kg=leftover_kg,
        leftover_util_pct=base.metal_utilization_pct,
        gaps=gaps,
        safe=False,
        unfixable=unfixable,
    )
    if best_pile is not None and best_total_kg not in (inf, 0.0):
        plan.booster_code = best_pile.code
        plan.booster_grade_au = best_pile.grade_au
        plan.booster_tier = best_pile.tier(must_fix[0]) if must_fix else ""
        plan.recommend_kg = best_total_kg
        after = value_blend(
            comps + [BlendComponent(best_pile, best_total_kg)], prices, terms
        )
        plan.after_util_pct = _leftover_utilization(base, after)
    return plan


def _leftover_utilization(base, after) -> float:
    """% del metal **del sobrante** que pasa a pagarse al mezclarlo con el refuerzo.

    Aislar el sobrante es clave: agregar una pila rica infla el metal total
    (denominador), así que el aprovechamiento de la mezcla combinada no es
    comparable. En cambio, valorizar el metal del sobrante con el RR de la mezcla
    completa mide el beneficio real — sube si y solo si la mezcla rescata metal
    que antes caía bajo el umbral.
    """
    gross = sum(r.gross_amount_usd for r in base.metals.values())
    if gross <= 0:
        return base.metal_utilization_pct
    paid = sum(
        base.metals[m].gross_amount_usd * after.metals[m].rr for m in base.metals
    )
    return 100.0 * paid / gross
