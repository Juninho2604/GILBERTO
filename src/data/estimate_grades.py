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


@dataclass
class GradeEstimate:
    """Ley estimada de una pila, con su origen y diagnóstico."""

    code: str
    name: str = ""
    grades: dict[str, float] = field(default_factory=dict)  # metal → ley
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
    return estimates


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
