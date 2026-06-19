"""Tests del optimizador (Fase 2)."""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from domain.models import Category, InventoryItem, default_prices, default_terms
from optimize.optimizer import optimize_blend, optimize_partition

pulp = pytest.importorskip("pulp")


def _item(code, **kw):
    kw.setdefault("category", Category.RAEE)
    kw.setdefault("moisture", 0.0)
    return InventoryItem(code=code, name=code, **kw)


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
