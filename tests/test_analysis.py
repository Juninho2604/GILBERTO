"""Tests del módulo de análisis: explicación y estudio del histórico."""

from __future__ import annotations

import pytest

from analysis.explain import explain_lot, explain_partition
from domain.models import (
    Category,
    InventoryItem,
    default_prices,
    default_terms,
)
from domain.valuation import BlendComponent, value_blend


def _item(code, **g):
    return InventoryItem(
        code=code, name=code, category=Category.RAEE, quantity_kg=1000.0,
        moisture=0.01, grade_cu=g.get("cu", 0.0), grade_au=g.get("au", 0.0),
        grade_ag=g.get("ag", 0.0), grade_pd=g.get("pd", 0.0),
    )


def test_explain_lot_marks_capped_gold():
    """Una pila muy rica en oro debe quedar con el RR de oro en el tope."""
    prices, terms = default_prices(), default_terms()
    rich = _item("001", au=400.0, cu=0.25)
    v = value_blend([BlendComponent(rich, 1000.0)], prices, terms)
    rat = explain_lot(v, terms)
    au_driver = next(d for d in rat.drivers if d.metal == "AU")
    assert au_driver.status == "capped"
    assert rat.role == "rico"


def test_explain_lot_flags_below_threshold():
    """Paladio bajo el umbral (18 g/t) se marca como sub-umbral (paga 0)."""
    prices, terms = default_prices(), default_terms()
    poor = _item("002", cu=0.20, pd=4.0)
    v = value_blend([BlendComponent(poor, 1000.0)], prices, terms)
    rat = explain_lot(v, terms)
    pd_driver = next(d for d in rat.drivers if d.metal == "PD")
    assert pd_driver.status == "below_threshold"


def test_explain_partition_arithmetic_and_roles():
    """La explicación suma bien los lotes, computa la ganancia y rotula roles."""
    prices, terms = default_prices(), default_terms()
    rich = _item("001", au=300.0, cu=0.25, ag=1200.0)
    filler = _item("002", au=5.0, cu=0.05)
    rich_v = value_blend([BlendComponent(rich, 1000.0)], prices, terms)
    filler_v = value_blend([BlendComponent(filler, 1000.0)], prices, terms)
    single = value_blend(
        [BlendComponent(rich, 1000.0), BlendComponent(filler, 1000.0)], prices, terms
    )
    expl = explain_partition([rich_v, filler_v], single, terms)
    # Identidad: el valor de la partición es la suma de los lotes.
    assert expl.partition_usd == pytest.approx(
        rich_v.net_value_usd + filler_v.net_value_usd
    )
    # La ganancia es exactamente partición − mezcla única (signo informativo).
    assert expl.gain_usd == pytest.approx(expl.partition_usd - single.net_value_usd)
    # Roles: el lote de oro es "rico"; el pobre, "relleno".
    roles = {l.role for l in expl.lots}
    assert "rico" in roles
    assert expl.bullets


def test_explain_partition_to_dict_is_serializable():
    """La explicación debe serializarse a tipos JSON (para la API/artefacto)."""
    import json

    prices, terms = default_prices(), default_terms()
    v = value_blend([BlendComponent(_item("001", au=100.0, cu=0.2), 1000.0)], prices, terms)
    expl = explain_partition([v], None, terms)
    json.dumps(expl.to_dict())  # no debe lanzar


@pytest.mark.skipif(
    not __import__("pathlib").Path("data/refining_history.xlsx").exists(),
    reason="requiere el xlsx del histórico",
)
def test_history_analysis_runs_and_is_faithful():
    """El estudio del histórico corre y el modelo es fiel al dinero real (<10%)."""
    from analysis.historical import analyze_history

    a = analyze_history()
    assert a.n_lots == 53
    assert a.n_resolvable > 20
    assert a.money_fidelity_pct < 10.0  # baseline estimado ≈ pago real
    assert a.sub_threshold_total_usd > 0  # hubo metal sub-umbral en el histórico
