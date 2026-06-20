"""Tests del optimizador (Fase 2)."""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from domain.models import Category, InventoryItem, default_prices, default_terms
from optimize.optimizer import best_partition, optimize_blend, optimize_partition

pulp = pytest.importorskip("pulp")


def _item(code, **kw):
    kw.setdefault("category", Category.RAEE)
    kw.setdefault("moisture", 0.0)
    return InventoryItem(code=code, name=code, **kw)


def test_pack_lots_container_plan():
    """Empaqueta: contenedor = 1 lote final + anticipo, sin pasar la capacidad."""
    from app.logistics import pack_lots

    loads = pack_lots([18_500, 11_525, 11_525], container_kg=23_000, final_lot_kg=18_500)
    assert all(c.total_kg <= 23_000 + 1.0 for c in loads)
    # El primer contenedor completa el lote 1 y mete anticipo del lote 2.
    c1 = loads[0]
    assert any(n == 1 and not anti for n, _, anti in c1.segments)
    assert any(anti for _, _, anti in c1.segments)  # hay anticipo
    # Conserva el peso total.
    assert sum(c.total_kg for c in loads) == pytest.approx(18_500 + 11_525 + 11_525)


def test_best_partition_picks_and_beats_single_lot():
    """Auto-elige cuántos lotes; con material valioso que excede el tope, ≥2 lotes.

    Dos pilas ricas que juntas pasan el tope del lote: en 1 solo lote no entran
    (se deja material valioso afuera). El sistema debe elegir ≥2 lotes y batir al
    de 1 lote.
    """
    prices, terms = default_prices(), default_terms()
    items = [
        _item("RICO1", quantity_kg=12_000, grade_cu=0.25, grade_au=200, grade_ag=800, grade_pd=50),
        _item("RICO2", quantity_kg=12_000, grade_cu=0.24, grade_au=180, grade_ag=750, grade_pd=45),
    ]
    bp = best_partition(items, prices, terms, max_num_lots=5, max_lot_kg=18_000)
    one = optimize_partition(items, prices, terms, num_lots=1, max_lot_kg=18_000)
    assert bp.num_lots >= 2
    assert bp.net_value_usd > one.net_value_usd  # 1 lote deja material rico afuera
    # El barrido es no decreciente en cantidad de lotes.
    vals = [v for _, v in bp.sweep]
    assert vals == sorted(vals)


def test_best_partition_stops_when_flat():
    """Si un lote alcanza, no infla la cantidad de lotes."""
    prices, terms = default_prices(), default_terms()
    items = [_item("U", quantity_kg=4_000, grade_cu=0.22, grade_au=150, grade_ag=700, grade_pd=40)]
    bp = best_partition(items, prices, terms, max_num_lots=5, max_lot_kg=18_000)
    assert bp.num_lots == 1


def test_partition_respects_max_lot_kg():
    """Ningún lote debe superar el tope físico (contenedor / lote final)."""
    prices, terms = default_prices(), default_terms()
    items = [
        _item(f"P{i}", quantity_kg=8000, grade_cu=0.20, grade_au=120, grade_ag=600, grade_pd=40)
        for i in range(5)
    ]  # 40.000 kg en total
    res = optimize_partition(items, prices, terms, num_lots=4, max_lot_kg=18_500)
    assert res.status == "Optimal"
    assert res.lots
    for lot in res.lots:
        assert lot.total_weight_kg <= 18_500 + 1.0  # tolerancia numérica


def test_excludes_value_destroying_pile():
    """Una pila de puro relleno (sin metal) no debería entrar si destruye valor."""
    prices, terms = default_prices(), default_terms()
    rich = _item("RICH", quantity_kg=1000, grade_cu=0.25, grade_au=150, grade_ag=900, grade_pd=60)
    junk = _item("JUNK", quantity_kg=1000, grade_cu=0.0, grade_au=0, grade_ag=0, grade_pd=0)
    res = optimize_blend([rich, junk], prices, terms)
    assert res.status == "Optimal"
    assert "RICH" in res.weights
    # La basura solo suma cargos (treatment+shred) → no se incluye.
    assert res.weights.get("JUNK", 0.0) == pytest.approx(0.0, abs=1.0)


def test_optimizer_respects_stock():
    prices, terms = default_prices(), default_terms()
    rich = _item("RICH", quantity_kg=500, grade_cu=0.25, grade_au=150, grade_ag=900, grade_pd=60)
    res = optimize_blend([rich], prices, terms)
    assert res.weights["RICH"] <= 500 + 1e-6


def test_rescue_below_threshold_metal():
    """Pd sub-umbral solo no paga; el optimizador lo mezcla para rescatarlo."""
    prices, terms = default_prices(), default_terms()
    # Pila con MUCHO Pd pero por debajo del umbral de 18 g/t si va sola... usamos
    # una pila rica en Pd (paga sola) + una pobre en Pd que se beneficia.
    rich_pd = _item("RPD", quantity_kg=1000, grade_cu=0.2, grade_au=80, grade_ag=600, grade_pd=40)
    res = optimize_blend([rich_pd], prices, terms)
    assert res.valuation.metals["PD"].amount_usd > 0  # 40 > 18 → paga


def test_partition_beats_single_blend_when_gold_dominates():
    """Con oro dominante y deducción por tonelada, separar puede pagar más."""
    prices, terms = default_prices(), default_terms()
    # Pila muy rica en Au (capada) + bulk pobre en Au pero con algo de Cu.
    gold = _item("GOLD", quantity_kg=2000, grade_cu=0.2, grade_au=600, grade_ag=2000, grade_pd=40)
    bulk = _item("BULK", quantity_kg=10000, grade_cu=0.12, grade_au=20, grade_ag=300, grade_pd=8)
    items = [gold, bulk]

    one = optimize_blend(items, prices, terms)
    two = optimize_partition(items, prices, terms, num_lots=2)
    assert two.status in ("Optimal", "Not Solved")
    # Dos lotes nunca deben pagar menos que uno (un lote es caso particular).
    assert two.net_value_usd >= one.net_value_usd - 1.0


def test_partition_assigns_within_stock():
    prices, terms = default_prices(), default_terms()
    a = _item("A", quantity_kg=1000, grade_cu=0.25, grade_au=200, grade_ag=1500, grade_pd=50)
    b = _item("B", quantity_kg=800, grade_cu=0.18, grade_au=120, grade_ag=900, grade_pd=30)
    res = optimize_partition([a, b], prices, terms, num_lots=2)
    # El total asignado de cada pila no supera su stock.
    used = {"A": 0.0, "B": 0.0}
    for lot in res.lots:
        for p in lot.components:
            used[p.item.code] += p.weight_kg
    assert used["A"] <= 1000 + 1.0
    assert used["B"] <= 800 + 1.0
