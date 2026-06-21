"""Estimación de leyes por pila desde el histórico (sección 6 del brief).

El inventario tiene peso pero **no** tiene ley. Cada lote histórico trae su
análisis real, que es el promedio ponderado (por peso seco) de las pilas que
lo formaron:

    grade_lot(m) = Σ_i  frac_i · grade_i(m)

Conocidas las recetas (fracciones ``frac_i``) y las leyes del lote, se despeja
la ley de cada pila resolviendo el sistema inverso por **mínimos cuadrados**.

Niveles de confianza del resultado:
- ``DIRECT``   — la pila apareció sola en uno o más lotes puros (medición
  directa; si hay repeticiones se promedian). Máxima confianza.
- ``ESTIMATED``— despejada por regresión desde recetas resolubles. Media.
- ``ASSUMED``  — solo aparece en recetas con grupos base ambiguos repartidos
  por igual; es un supuesto. Baja confianza.

La aproximación usa las fracciones de la receta como fracciones de peso seco
(las humedades por pila dentro de un lote no se conocen y son pequeñas). Es un
método **prometedor pero a validar** contra los ensayos reales.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from statistics import pstdev
from typing import Iterable, Optional

import numpy as np

from domain.models import METALS, GradeSource, InventoryItem

from .load_history import HistoricLot, load_history
from .load_inventory import load_raee_inventory


class Confidence(str, Enum):
    DIRECT = "direct"        # lote puro (medición directa)
    ESTIMATED = "estimated"  # regresión sobre recetas resolubles
    ASSUMED = "assumed"      # reparto equitativo de bases ambiguas
    NONE = "none"            # sin datos (pendiente laboratorio)


# Tier de confianza por (pila, metal) — Feature 1 del change-order.
TIER_MEASURED = "MEASURED"            # la pila viajó sola (análisis directo)
TIER_ESTIMATED = "ESTIMATED"          # separable en la regresión, con σ acotado
TIER_NOT_DETERMINED = "NOT_DETERMINED"  # bloque colineal, o σ ≥ valor

# Ruido por defecto (CV) cuando hay una sola medición directa. Conservador.
CV_DEFAULT: dict[str, float] = {"CU": 0.05, "AU": 0.15, "AG": 0.30, "PD": 0.30, "PT": 0.30}


@dataclass
class Grade:
    """Una ley con su margen de error y nivel de confianza (por metal)."""

    value: float                       # ley estimada/medida
    sigma: float = 0.0                 # 1 desviación estándar (error absoluto)
    tier: str = TIER_NOT_DETERMINED    # MEASURED | ESTIMATED | NOT_DETERMINED
    n_direct: int = 0                  # nº de veces que la pila viajó sola
    source: str = "regression"         # replicates | regression | colinear_block


@dataclass
class GradeEstimate:
    """Ley estimada de una pila, con su origen y diagnóstico."""

    code: str
    name: str = ""
    grades: dict[str, float] = field(default_factory=dict)  # metal → ley (valor puntual)
    sigmas: dict[str, float] = field(default_factory=dict)  # metal → σ (margen de error)
    tiers: dict[str, str] = field(default_factory=dict)     # metal → tier de confianza
    block: Optional[tuple] = None       # miembros del bloque colineal si la pila está en uno
    confidence: Confidence = Confidence.NONE
    n_pure_lots: int = 0          # cuántas veces apareció sola
    n_recipes: int = 0            # en cuántas recetas (resolubles) aparece
    rel_spread: Optional[float] = None  # dispersión relativa entre lotes puros
    note: str = ""

    @property
    def source(self) -> GradeSource:
        if self.confidence == Confidence.DIRECT:
            return GradeSource.LAB  # tratamos la medición directa como dato duro
        return GradeSource.ESTIMATED

    def grade(self, metal: str) -> Grade:
        """Devuelve la :class:`Grade` (valor + σ + tier) de un metal."""
        return Grade(
            value=self.grades.get(metal, 0.0),
            sigma=self.sigmas.get(metal, 0.0),
            tier=self.tiers.get(metal, TIER_NOT_DETERMINED),
            n_direct=self.n_pure_lots,
            source="colinear_block" if self.block else (
                "replicates" if self.n_pure_lots else "regression"),
        )


# --------------------------------------------------------------------------- #
# Estimación
# --------------------------------------------------------------------------- #
def estimate_grades(
    lots: Optional[list[HistoricLot]] = None,
    names: Optional[dict[str, str]] = None,
) -> dict[str, GradeEstimate]:
    """Estima la ley de cada pila a partir de los lotes históricos.

    Devuelve ``{code: GradeEstimate}``.
    """
    if lots is None:
        lots = load_history()
    names = names or {}

    # 1) Mediciones directas: lotes puros (una sola pila, fracción 1).
    pure_obs: dict[str, list[dict[str, float]]] = {}
    for L in lots:
        if L.recipe.resolvable and len(L.recipe.fractions) == 1:
            (code, frac), = L.recipe.fractions.items()
            if abs(frac - 1.0) < 1e-6:
                pure_obs.setdefault(code, []).append(L.grades)

    estimates: dict[str, GradeEstimate] = {}
    for code, obs in pure_obs.items():
        grades = {m: float(np.mean([o.get(m, 0.0) for o in obs])) for m in METALS}
        # Dispersión relativa (sobre Au, suele ser el de mayor valor).
        spread = None
        if len(obs) > 1:
            au = [o.get("AU", 0.0) for o in obs]
            mean_au = np.mean(au)
            spread = float(pstdev(au) / mean_au) if mean_au else None
        estimates[code] = GradeEstimate(
            code=code,
            name=names.get(code, ""),
            grades=grades,
            confidence=Confidence.DIRECT,
            n_pure_lots=len(obs),
            rel_spread=spread,
            note=f"medición directa ({len(obs)} lote/s puro/s)",
        )

    # 2) Regresión por mínimos cuadrados sobre recetas resolubles.
    #    Resolvemos por metal: A x = b, con A = matriz de fracciones.
    resolvable = [L for L in lots if L.recipe.resolvable]
    codes = sorted({c for L in resolvable for c in L.recipe.fractions})
    idx = {c: i for i, c in enumerate(codes)}
    if codes:
        A = np.zeros((len(resolvable), len(codes)))
        for r, L in enumerate(resolvable):
            for c, f in L.recipe.fractions.items():
                A[r, idx[c]] = f
        recipe_count = {c: int((A[:, idx[c]] > 0).sum()) for c in codes}

        for metal in METALS:
            b = np.array([L.grades.get(metal, 0.0) for L in resolvable])
            x, *_ = np.linalg.lstsq(A, b, rcond=None)
            x = np.clip(x, 0.0, None)  # leyes no negativas
            for c in codes:
                est = estimates.get(c)
                if est is None:
                    est = GradeEstimate(
                        code=c, name=names.get(c, ""),
                        confidence=Confidence.ESTIMATED,
                        n_recipes=recipe_count[c],
                        note="regresión sobre recetas resolubles",
                    )
                    estimates[c] = est
                est.n_recipes = recipe_count[c]
                # Solo sobreescribir leyes de los que NO son medición directa.
                if est.confidence != Confidence.DIRECT:
                    est.grades[metal] = float(x[idx[c]])

    # 3) Bases ambiguas (reparto equitativo) para pilas aún sin estimación.
    ambiguous = [L for L in lots if (not L.recipe.resolvable) and L.recipe.assumed_equal_split]
    amb_codes = sorted({c for L in ambiguous for c in L.recipe.fractions})
    missing = [c for c in amb_codes if c not in estimates]
    if missing:
        rel = [L for L in ambiguous]
        amb_idx = {c: i for i, c in enumerate(missing)}
        # Para cada lote ambiguo, restamos el aporte de pilas ya conocidas.
        rows, metal_b = [], {m: [] for m in METALS}
        for L in rel:
            row = np.zeros(len(missing))
            known_contrib = {m: 0.0 for m in METALS}
            has_missing = False
            for c, f in L.recipe.fractions.items():
                if c in amb_idx:
                    row[amb_idx[c]] = f
                    has_missing = True
                elif c in estimates:
                    for m in METALS:
                        known_contrib[m] += f * estimates[c].grades.get(m, 0.0)
            if not has_missing:
                continue
            rows.append(row)
            for m in METALS:
                metal_b[m].append(L.grades.get(m, 0.0) - known_contrib[m])
        if rows:
            Aa = np.vstack(rows)
            counts = {c: int((Aa[:, amb_idx[c]] > 0).sum()) for c in missing}
            for m in METALS:
                xa, *_ = np.linalg.lstsq(Aa, np.array(metal_b[m]), rcond=None)
                xa = np.clip(xa, 0.0, None)
                for c in missing:
                    est = estimates.setdefault(
                        c,
                        GradeEstimate(
                            code=c, name=names.get(c, ""),
                            confidence=Confidence.ASSUMED,
                            n_recipes=counts[c],
                            note="grupo base ambiguo; reparto equitativo (supuesto)",
                        ),
                    )
                    est.grades[m] = float(xa[amb_idx[c]])

    # Completar nombres.
    for c, est in estimates.items():
        if not est.name:
            est.name = names.get(c, "")

    # Confianza por (pila, metal): σ, tier, bloques colineales (Feature 1).
    _compute_confidence(lots, estimates)
    return estimates


# --------------------------------------------------------------------------- #
# Confianza por (pila, metal): σ, tier y bloques colineales
# --------------------------------------------------------------------------- #
def _colinear_blocks(lots: list[HistoricLot]) -> dict[str, tuple]:
    """Pilas que SOLO viajaron juntas (columnas proporcionales) → no separables.

    Devuelve ``{code: (miembros del bloque)}``. Dos pilas están confundidas si su
    columna en la matriz de recetas es proporcional (mismo patrón de aparición y
    ratio constante): la regresión no puede despejar sus leyes individuales.
    """
    withfr = [L for L in lots if L.recipe.fractions]
    codes = sorted({c for L in withfr for c in L.recipe.fractions})
    if not codes:
        return {}
    idx = {c: i for i, c in enumerate(codes)}
    A = np.zeros((len(withfr), len(codes)))
    for r, L in enumerate(withfr):
        for c, f in L.recipe.fractions.items():
            A[r, idx[c]] = f

    sig2codes: dict[tuple, list[str]] = {}
    for c in codes:
        col = A[:, idx[c]]
        nz = np.flatnonzero(np.abs(col) > 1e-9)
        if len(nz) == 0:
            continue
        v = col[nz] / np.linalg.norm(col[nz])
        sig = (tuple(nz.tolist()), tuple(np.round(v, 6).tolist()))
        sig2codes.setdefault(sig, []).append(c)

    blocks: dict[str, tuple] = {}
    for members in sig2codes.values():
        if len(members) >= 2:
            tup = tuple(sorted(members))
            for c in members:
                blocks[c] = tup
    return blocks


def _regression_se(lots: list[HistoricLot]) -> dict[tuple, float]:
    """Error estándar de cada (pila, metal) en la regresión sobre lotes resolubles.

    ``SE_j = sqrt(σ²_residual · [ (AᵀA)⁺ ]_jj )``. Para columnas confundidas el
    pinv da valores poco fiables; por eso los bloques colineales se marcan aparte.
    """
    resolv = [L for L in lots if L.recipe.resolvable]
    rcodes = sorted({c for L in resolv for c in L.recipe.fractions})
    se: dict[tuple, float] = {}
    if not rcodes or len(resolv) <= 1:
        return se
    ridx = {c: i for i, c in enumerate(rcodes)}
    A = np.zeros((len(resolv), len(rcodes)))
    for r, L in enumerate(resolv):
        for c, f in L.recipe.fractions.items():
            A[r, ridx[c]] = f
    rank = int(np.linalg.matrix_rank(A))
    dof = max(1, len(resolv) - rank)
    ata_pinv = np.linalg.pinv(A.T @ A)
    diag = np.clip(np.diag(ata_pinv), 0.0, None)
    for m in METALS:
        b = np.array([L.grades.get(m, 0.0) for L in resolv])
        x, *_ = np.linalg.lstsq(A, b, rcond=None)
        resid = b - A @ x
        s2 = float(resid @ resid) / dof
        for c in rcodes:
            se[(c, m)] = float(np.sqrt(s2 * diag[ridx[c]]))
    return se


def _pure_observations(lots: list[HistoricLot]) -> dict[str, list[dict]]:
    """Leyes de los lotes puros (una pila, fracción 1) → mediciones directas."""
    obs: dict[str, list[dict]] = {}
    for L in lots:
        if L.recipe.resolvable and len(L.recipe.fractions) == 1:
            (c, f), = L.recipe.fractions.items()
            if abs(f - 1.0) < 1e-6:
                obs.setdefault(c, []).append(L.grades)
    return obs


# Apalancamiento mínimo: una pila que nunca fue ≥10% de ningún lote queda mal
# determinada por la regresión (caso pila 26: 2% de un solo lote → no usable).
MIN_LEVERAGE = 0.10


def _compute_confidence(
    lots: list[HistoricLot], estimates: dict[str, GradeEstimate]
) -> None:
    """Asigna σ y tier por (pila, metal) y marca bloques colineales. Muta in place."""
    pure = _pure_observations(lots)
    blocks = _colinear_blocks(lots)
    se = _regression_se(lots)

    # Apalancamiento: mayor fracción que tuvo cada pila en un lote resoluble.
    max_frac: dict[str, float] = {}
    for L in lots:
        if not L.recipe.resolvable:
            continue
        for c, f in L.recipe.fractions.items():
            max_frac[c] = max(max_frac.get(c, 0.0), f)

    for c, est in estimates.items():
        est.block = blocks.get(c)
        low_leverage = max_frac.get(c, 0.0) < MIN_LEVERAGE
        for m in METALS:
            val = est.grades.get(m, 0.0)
            cv = CV_DEFAULT.get(m, 0.3)
            if c in pure:                          # MEASURED (viajó sola)
                vals = [o.get(m, 0.0) for o in pure[c]]
                sigma = float(np.std(vals, ddof=1)) if len(vals) >= 2 else val * cv
                if sigma <= 0:
                    sigma = val * cv
                tier = TIER_MEASURED
            elif c in blocks:                      # confundida en un bloque
                sigma = val * cv
                tier = TIER_NOT_DETERMINED
            elif low_leverage:                     # nunca fue parte significativa
                sigma = se.get((c, m), val * cv)
                tier = TIER_NOT_DETERMINED
            else:                                  # despejada por regresión
                sigma = se.get((c, m), val * cv)
                tier = TIER_ESTIMATED
            # Regla universal: si el error iguala o supera al valor, no es usable.
            if val > 0 and sigma >= val:
                tier = TIER_NOT_DETERMINED
            est.sigmas[m] = sigma
            est.tiers[m] = tier


def reconstruction_report(
    lots: Optional[list[HistoricLot]] = None,
    estimates: Optional[dict[str, GradeEstimate]] = None,
) -> list[dict]:
    """Valida la estimación: predice la ley de cada lote y la compara con la real.

    Para cada lote resoluble, ``pred(m) = Σ frac_i · grade_i(m)`` y se compara
    con la ley observada. Un error chico = estimación coherente.
    """
    if lots is None:
        lots = load_history()
    if estimates is None:
        estimates = estimate_grades(lots)

    out = []
    for L in lots:
        if not L.recipe.resolvable:
            continue
        pred = {}
        for m in METALS:
            pred[m] = sum(
                f * estimates[c].grades.get(m, 0.0)
                for c, f in L.recipe.fractions.items()
                if c in estimates
            )
        row = {"customer_lot": L.customer_lot, "recipe": L.recipe_raw}
        for m in METALS:
            actual = L.grades.get(m, 0.0)
            row[f"{m}_actual"] = actual
            row[f"{m}_pred"] = pred[m]
            row[f"{m}_err%"] = (
                100.0 * (pred[m] - actual) / actual if actual else 0.0
            )
        out.append(row)
    return out


def apply_estimates_to_inventory(
    items: Iterable[InventoryItem],
    estimates: dict[str, GradeEstimate],
) -> list[InventoryItem]:
    """Carga las leyes estimadas en los ítems de inventario (marca el origen)."""
    out = []
    for it in items:
        est = estimates.get(it.code)
        if est:
            it.grade_cu = est.grades.get("CU", 0.0)
            it.grade_au = est.grades.get("AU", 0.0)
            it.grade_ag = est.grades.get("AG", 0.0)
            it.grade_pt = est.grades.get("PT", 0.0)
            it.grade_pd = est.grades.get("PD", 0.0)
            it.grade_source = est.source
            it.grade_confidence = {
                Confidence.DIRECT: 0.9,
                Confidence.ESTIMATED: 0.6,
                Confidence.ASSUMED: 0.3,
                Confidence.NONE: None,
            }[est.confidence]
            it.grade_sigma = dict(est.sigmas)
            it.grade_tier = dict(est.tiers)
        out.append(it)
    return out


if __name__ == "__main__":  # pragma: no cover
    inv = load_raee_inventory(with_stock_only=False)
    names = {it.code: it.name for it in inv}
    est = estimate_grades(names=names)

    stocked = {it.code for it in inv if it.quantity_kg > 0}
    covered = stocked & set(est)
    print(f"Pilas RAEE con stock: {len(stocked)} | con ley estimada: {len(covered)} "
          f"| pendientes: {len(stocked - covered)}")
    print()
    print(f"{'code':>4} {'conf':<9} {'CU':>7} {'AU':>8} {'AG':>8} {'PD':>7}  name")
    for c in sorted(est, key=lambda c: (est[c].confidence.value, c)):
        e = est[c]
        if c not in stocked:
            continue
        g = e.grades
        print(f"{c:>4} {e.confidence.value:<9} {g.get('CU',0):>7.3f} {g.get('AU',0):>8.1f} "
              f"{g.get('AG',0):>8.0f} {g.get('PD',0):>7.1f}  {e.name}")
