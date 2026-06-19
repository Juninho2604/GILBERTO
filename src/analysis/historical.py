"""Estudio del histórico: real vs. óptimo, y cuánto se hubiera ganado de más.

Cada uno de los 53 lotes históricos trae su **análisis real medido** por la
refinería (ley por metal), su peso y su receta. Con eso construimos tres
mundos comparables:

1. **Real (medido)** — el dinero que efectivamente pagó la refinería, usando
   las leyes medidas del lote. Es la verdad de terreno.
2. **Modelo "tal cual" (estimado)** — reconstruimos las pilas del lote desde la
   receta y las valorizamos con nuestras **leyes estimadas**, combinadas como
   las combinó Gilberto. Sirve para mostrar que el modelo reproduce el dinero
   real (validación a nivel plata, no solo a nivel ley).
3. **Modelo óptimo (estimado)** — tomamos exactamente ese mismo material y
   dejamos que el optimizador decida la mejor partición. La diferencia contra
   (2) aísla el efecto de **la decisión de mezcla** (no del error de estimación,
   porque ambos usan las mismas leyes estimadas).

El titular del negocio: cuánto más (en USD y en %) habría pagado la refinería
si cada lote se hubiera armado con el optimizador en vez de a mano.

Además, desde las **leyes medidas** (verdad de terreno) detectamos el metal que
quedó **por debajo del umbral de deducción** y por lo tanto pagó 0: es plata/
paladio físicamente presente que se perdió por no mezclar. Su valor a precio
spot es el techo teórico de lo rescatable.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Optional

from analysis.explain import explain_partition
from data.estimate_grades import GradeEstimate, estimate_grades, reconstruction_report
from data.load_history import HistoricLot, load_history
from data.load_inventory import load_raee_inventory
from domain.models import (
    METALS,
    PRECIOUS_METALS,
    TROY_OUNCE_G,
    Category,
    ContractTerms,
    GradeSource,
    InventoryItem,
    MetalPrices,
    default_prices,
    default_terms,
)
from domain.valuation import BlendComponent, value_blend, value_lot
from optimize.optimizer import optimize_partition

_USD = "${:,.0f}".format


# --------------------------------------------------------------------------- #
# Estructuras de salida (serializables a JSON para la API)
# --------------------------------------------------------------------------- #
@dataclass
class SubThresholdLoss:
    """Metal que pagó 0 por quedar bajo el umbral de deducción (verdad medida)."""

    metal: str
    grade: float
    threshold: float
    content_g: float
    gross_value_usd: float   # valor a spot del metal sub-umbral (techo de rescate)


@dataclass
class LotComparison:
    """Comparación real vs. óptimo de un lote histórico."""

    customer_lot: object
    jx_lot: object
    recipe_raw: str
    resolvable: bool
    n_components: int
    wmt: float
    moisture: float
    dmt: float
    actual_grades: dict[str, float]
    actual_net_usd: float
    actual_per_kg: float
    # Mundo del modelo (solo si la receta es resoluble)
    model_aswas_usd: Optional[float] = None
    model_optimal_usd: Optional[float] = None
    optimal_num_lots: Optional[int] = None
    extra_usd: Optional[float] = None
    extra_pct: Optional[float] = None
    components: list[dict] = field(default_factory=list)
    explanation: Optional[dict] = None
    sub_threshold: list[dict] = field(default_factory=list)
    note: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class MetalPrecision:
    metal: str
    n: int
    median_abs_err_pct: float
    mean_abs_err_pct: float


@dataclass
class HistoryAnalysis:
    """Resultado completo del estudio del histórico."""

    n_lots: int
    n_resolvable: int
    # Dinero (verdad de terreno, leyes medidas)
    actual_total_usd: float
    actual_total_resolvable_usd: float
    # Modelo (leyes estimadas) sobre los lotes resolubles
    model_baseline_usd: float        # "tal cual" — como lo armó Gilberto
    model_optimal_usd: float         # re-optimizado lote por lote
    extra_usd: float
    extra_pct: float
    # Validación
    precision: list[MetalPrecision] = field(default_factory=list)
    money_fidelity_pct: float = 0.0  # |baseline_estimado − real| / real, en %
    # Rescate teórico desde la verdad medida
    sub_threshold_total_usd: float = 0.0
    coverage: dict = field(default_factory=dict)
    lots: list[LotComparison] = field(default_factory=list)

    def to_dict(self) -> dict:
        d = asdict(self)
        return d


# --------------------------------------------------------------------------- #
# Reconstrucción de las pilas de un lote
# --------------------------------------------------------------------------- #
def _reconstruct_items(
    lot: HistoricLot, estimates: dict[str, GradeEstimate], names: dict[str, str]
) -> list[InventoryItem]:
    """Pilas (con kg y leyes estimadas) que formaron un lote resoluble."""
    items: list[InventoryItem] = []
    for code, frac in lot.recipe.fractions.items():
        est = estimates.get(code)
        if est is None or frac <= 0:
            continue
        items.append(
            InventoryItem(
                code=code,
                name=names.get(code, code),
                category=Category.RAEE,
                quantity_kg=frac * lot.wmt,
                moisture=lot.moisture,
                grade_cu=est.grades.get("CU", 0.0),
                grade_au=est.grades.get("AU", 0.0),
                grade_ag=est.grades.get("AG", 0.0),
                grade_pt=est.grades.get("PT", 0.0),
                grade_pd=est.grades.get("PD", 0.0),
                grade_source=est.source,
            )
        )
    return items


def _sub_threshold_losses(
    lot: HistoricLot, prices: MetalPrices, terms: ContractTerms
) -> list[SubThresholdLoss]:
    """Metal medido que pagó 0 por estar bajo el umbral (techo de rescate a spot)."""
    out: list[SubThresholdLoss] = []
    for metal in PRECIOUS_METALS:
        rule = terms.rule(metal)
        if not rule.paid:
            continue
        grade = lot.grades.get(metal, 0.0)
        if grade <= 0 or grade > rule.deduction:
            continue  # paga algo o no hay metal
        content_g = (lot.dmt / 1000.0) * grade
        unit = max(0.0, prices.price(metal) - terms.rc(metal))
        gross = content_g * unit / TROY_OUNCE_G
        if gross <= 0:
            continue
        out.append(
            SubThresholdLoss(
                metal=metal,
                grade=grade,
                threshold=rule.deduction,
                content_g=content_g,
                gross_value_usd=gross,
            )
        )
    return out


def _best_partition(items, prices, terms, max_lots: int):
    """Mejor partición probando 1..max_lots lotes; devuelve (result, k)."""
    best, best_k = None, 1
    for k in range(1, max_lots + 1):
        res = optimize_partition(items, prices, terms, num_lots=k, time_limit_s=8.0)
        if res.lots and (best is None or res.net_value_usd > best.net_value_usd + 1e-6):
            best, best_k = res, k
    return best, best_k


# --------------------------------------------------------------------------- #
# Análisis de un lote
# --------------------------------------------------------------------------- #
def analyze_lot(
    lot: HistoricLot,
    estimates: dict[str, GradeEstimate],
    names: dict[str, str],
    prices: MetalPrices,
    terms: ContractTerms,
) -> LotComparison:
    # Verdad de terreno: valorización con las leyes MEDIDAS del lote.
    actual = value_lot(lot.wmt, lot.moisture, lot.grades, prices, terms)
    sub = _sub_threshold_losses(lot, prices, terms)

    comp = LotComparison(
        customer_lot=lot.customer_lot,
        jx_lot=lot.jx_lot,
        recipe_raw=lot.recipe_raw,
        resolvable=lot.recipe.resolvable,
        n_components=len(lot.recipe.fractions),
        wmt=lot.wmt,
        moisture=lot.moisture,
        dmt=lot.dmt,
        actual_grades=dict(lot.grades),
        actual_net_usd=actual.net_value_usd,
        actual_per_kg=actual.result_per_kg,
        sub_threshold=[asdict(s) for s in sub],
        note=lot.recipe.note,
    )

    if not lot.recipe.resolvable:
        return comp

    items = _reconstruct_items(lot, estimates, names)
    if not items:
        comp.resolvable = False
        return comp

    # (2) Modelo "tal cual": una sola mezcla con las leyes estimadas.
    aswas = value_blend([BlendComponent(it, it.quantity_kg) for it in items], prices, terms)

    # (3) Modelo óptimo: re-partición del mismo material.
    max_lots = min(3, len(items))
    best, best_k = _best_partition(items, prices, terms, max_lots)
    if best is None:
        comp.model_aswas_usd = aswas.net_value_usd
        return comp

    optimal_usd = best.net_value_usd
    extra = optimal_usd - aswas.net_value_usd
    comp.model_aswas_usd = aswas.net_value_usd
    comp.model_optimal_usd = optimal_usd
    comp.optimal_num_lots = best_k
    comp.extra_usd = extra
    comp.extra_pct = (100.0 * extra / aswas.net_value_usd) if aswas.net_value_usd else 0.0
    comp.components = [
        {
            "code": it.code,
            "name": names.get(it.code, it.code),
            "kg": round(it.quantity_kg, 1),
            "grade_au": round(it.grade_au, 1),
            "grade_ag": round(it.grade_ag, 0),
            "grade_cu": round(it.grade_cu, 4),
            "grade_pd": round(it.grade_pd, 1),
        }
        for it in sorted(items, key=lambda i: -i.quantity_kg)
    ]

    # Explicación: óptimo vs. la alternativa ingenua (todo junto = "tal cual").
    expl = explain_partition([l.valuation for l in best.lots], aswas, terms)
    comp.explanation = expl.to_dict()
    return comp


# --------------------------------------------------------------------------- #
# Análisis completo del histórico
# --------------------------------------------------------------------------- #
def analyze_history(
    prices: Optional[MetalPrices] = None,
    terms: Optional[ContractTerms] = None,
) -> HistoryAnalysis:
    prices = prices or default_prices()
    terms = terms or default_terms()

    lots = load_history()
    inv = load_raee_inventory(with_stock_only=False)
    names = {it.code: it.name for it in inv}
    estimates = estimate_grades(lots, names=names)

    comparisons = [analyze_lot(L, estimates, names, prices, terms) for L in lots]

    resolvable = [c for c in comparisons if c.resolvable and c.model_optimal_usd is not None]
    actual_total = sum(c.actual_net_usd for c in comparisons)
    actual_total_res = sum(c.actual_net_usd for c in resolvable)
    baseline = sum(c.model_aswas_usd for c in resolvable)
    optimal = sum(c.model_optimal_usd for c in resolvable)
    extra = optimal - baseline
    extra_pct = (100.0 * extra / baseline) if baseline else 0.0

    # Validación de la estimación (error de reconstrucción de leyes).
    rep = reconstruction_report(lots, estimates)
    precision: list[MetalPrecision] = []
    for m in ("CU", "AU", "AG", "PD"):
        errs = sorted(abs(r[f"{m}_err%"]) for r in rep if r[f"{m}_actual"] > 0)
        if errs:
            n = len(errs)
            median = errs[n // 2] if n % 2 else (errs[n // 2 - 1] + errs[n // 2]) / 2
            precision.append(
                MetalPrecision(m, n, round(median, 1), round(sum(errs) / n, 1))
            )

    money_fidelity = (
        100.0 * abs(baseline - actual_total_res) / actual_total_res
        if actual_total_res else 0.0
    )
    sub_total = sum(
        s["gross_value_usd"] for c in comparisons for s in c.sub_threshold
    )

    stocked = {it.code for it in inv if it.quantity_kg > 0}
    coverage = {
        "stocked_items": len(stocked),
        "covered": len(stocked & set(estimates)),
        "pending": len(stocked - set(estimates)),
    }

    return HistoryAnalysis(
        n_lots=len(comparisons),
        n_resolvable=len(resolvable),
        actual_total_usd=actual_total,
        actual_total_resolvable_usd=actual_total_res,
        model_baseline_usd=baseline,
        model_optimal_usd=optimal,
        extra_usd=extra,
        extra_pct=extra_pct,
        precision=precision,
        money_fidelity_pct=round(money_fidelity, 1),
        sub_threshold_total_usd=sub_total,
        coverage=coverage,
        lots=comparisons,
    )


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #
def _print_summary(a: HistoryAnalysis) -> None:
    print("=" * 72)
    print("ESTUDIO DEL HISTÓRICO — Real vs. Óptimo")
    print("=" * 72)
    print(f"\nLotes: {a.n_lots} | resolubles (con receta): {a.n_resolvable}")
    print(f"Cobertura de leyes: {a.coverage['covered']}/{a.coverage['stocked_items']} "
          f"pilas con stock.")
    print("\n[Validación de leyes estimadas — error de reconstrucción]")
    for p in a.precision:
        print(f"   {p.metal}: mediana |err| = {p.median_abs_err_pct:4.1f}%  (n={p.n})")
    print(f"   Fidelidad a nivel dinero (baseline estimado vs real): "
          f"{a.money_fidelity_pct:.1f}% de desvío.")

    print("\n[Cuánto se hubiera ganado de más con el optimizador]")
    print(f"   Modelo 'tal cual' (como se armó) : {_USD(a.model_baseline_usd)}")
    print(f"   Modelo óptimo (re-optimizado)    : {_USD(a.model_optimal_usd)}")
    print(f"   → Extra: {_USD(a.extra_usd)}  ({a.extra_pct:+.1f}%) sobre "
          f"{a.n_resolvable} lotes resolubles.")
    print(f"\n[Verdad de terreno — pago real medido]")
    print(f"   Total pagado (todos los lotes)   : {_USD(a.actual_total_usd)}")
    print(f"   Metal sub-umbral perdido (techo) : {_USD(a.sub_threshold_total_usd)} "
          f"(plata/paladio que pagó 0 por no mezclar).")

    top = sorted(
        (c for c in a.lots if c.extra_usd),
        key=lambda c: -(c.extra_usd or 0),
    )[:8]
    print("\n[Lotes con mayor oportunidad perdida]")
    for c in top:
        print(f"   Lote {str(c.customer_lot):>4}  receta {c.recipe_raw:<22} "
              f"tal cual {_USD(c.model_aswas_usd):>10} → óptimo "
              f"{_USD(c.model_optimal_usd):>10}  (+{_USD(c.extra_usd)}, "
              f"{c.extra_pct:+.0f}%)")
    print("=" * 72)


if __name__ == "__main__":  # pragma: no cover
    _print_summary(analyze_history())
