"""Tests de completar el contenedor (analysis.complete_container)."""

from analysis.complete_container import analyze_completion
from domain.models import Category, InventoryItem, default_prices, default_terms


def _item(code, kg, *, au=0.0, ag=0.0, pd=0.0, cu=0.21, moisture=0.01,
          tier="MEASURED", sigma=0.0):
    it = InventoryItem(
        code=code, name=code, category=Category.RAEE, quantity_kg=kg,
        moisture=moisture, grade_cu=cu, grade_au=au, grade_ag=ag, grade_pd=pd,
    )
    it.grade_tier = {m: tier for m in ("AU", "AG", "PD")}
    it.grade_sigma = {m: sigma for m in ("AU", "AG", "PD")}
    return it


def _prices_terms():
    return default_prices(), default_terms()


def test_safe_leftover_needs_no_purchase():
    # Sobrante ya rico: todos los metales por encima del umbral.
    prices, terms = _prices_terms()
    left = [_item("A", 5000, au=80, ag=400, pd=60)]
    plan = analyze_completion(left, left, prices, terms)
    assert plan.safe
    assert plan.recommend_kg == 0.0
    assert not plan.gaps


def test_detects_metal_below_threshold():
    # Pd a 12 g/t (umbral 18) en un sobrante pobre → paga $0.
    prices, terms = _prices_terms()
    left = [_item("LOW", 15000, au=40, ag=300, pd=12)]
    catalog = left + [_item("RICH", 3000, au=300, ag=600, pd=200)]
    plan = analyze_completion(left, catalog, prices, terms)
    assert not plan.safe
    pd_gap = next(g for g in plan.gaps if g.metal == "PD")
    assert pd_gap.below
    assert pd_gap.fixable


def test_recommends_reliable_pile_over_ghost_grade():
    # Una pila "fantasma" (NOT_DETERMINED) riquísima no debe recomendarse;
    # sí una medida algo menos rica.
    prices, terms = _prices_terms()
    left = [_item("LOW", 15000, au=40, ag=300, pd=12)]
    ghost = _item("GHOST", 50, pd=2000, tier="NOT_DETERMINED", sigma=800)
    real = _item("REAL", 3000, au=300, pd=160, tier="MEASURED", sigma=40)
    plan = analyze_completion(left, [left[0], ghost, real], prices, terms)
    assert plan.booster_code == "REAL"
    pd_gap = next(g for g in plan.gaps if g.metal == "PD")
    assert pd_gap.booster_code == "REAL"


def test_completion_raises_leftover_utilization():
    prices, terms = _prices_terms()
    left = [_item("LOW", 15000, au=40, ag=300, pd=12)]
    catalog = left + [_item("RICH", 3000, au=300, ag=600, pd=200)]
    plan = analyze_completion(left, catalog, prices, terms)
    assert plan.after_util_pct >= plan.leftover_util_pct
    assert plan.recommend_kg > 0


def test_unfixable_when_no_reliable_rich_pile():
    # Solo hay una pila Pd-rica pero sin determinar → Pd no rescatable.
    prices, terms = _prices_terms()
    left = [_item("LOW", 15000, au=80, ag=400, pd=12)]
    ghost = _item("GHOST", 50, pd=2000, tier="NOT_DETERMINED", sigma=800)
    plan = analyze_completion(left, [left[0], ghost], prices, terms)
    assert "PD" in plan.unfixable
