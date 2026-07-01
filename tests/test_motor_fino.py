"""Tests del motor fino (v1.3): CV calibrados, humedad estimada, rotación."""

import pytest

from data.estimate_grades import CV_DEFAULT, calibrate_cvs, estimate_moisture
from data.load_history import HistoricLot
from data.recipes import parse_recipe
from domain.models import Category, InventoryItem, default_prices, default_terms
from optimize.optimizer import rotation_plan


def _lot(cust, recipe, wmt=1000.0, moisture=0.02, **grades):
    g = {"CU": 0.0, "AU": 0.0, "AG": 0.0, "PT": 0.0, "PD": 0.0}
    g.update({k.upper(): v for k, v in grades.items()})
    return HistoricLot(
        customer_lot=cust, jx_lot=f"jx{cust}", wmt=wmt, moisture=moisture,
        dmt=wmt * (1 - moisture), grades=g, recipe_raw=recipe,
        recipe=parse_recipe(recipe),
    )


# --- CV calibrados desde lotes puros repetidos -------------------------------- #
def test_cv_calibrado_desde_repeticiones():
    # La pila 5 viajó sola 3 veces con Au 90/100/110 → CV medido ≈ 10/100 = 10%.
    lots = [
        _lot(1, "5", au=90.0), _lot(2, "5", au=100.0), _lot(3, "5", au=110.0),
    ]
    cvs = calibrate_cvs(lots)
    assert cvs["AU"] == pytest.approx(0.10, abs=0.01)


def test_cv_sin_repeticiones_cae_al_default():
    lots = [_lot(1, "5", au=100.0)]  # una sola observación: no calibra
    cvs = calibrate_cvs(lots)
    assert cvs["AU"] == CV_DEFAULT["AU"]
    assert cvs["AG"] == CV_DEFAULT["AG"]


# --- Humedad estimada desde el histórico -------------------------------------- #
def test_humedad_ponderada_por_lotes():
    # La pila 5 viajó en dos lotes: 1000 kg al 2% y 3000 kg al 4% → 3.5%.
    lots = [
        _lot(1, "5", wmt=1000.0, moisture=0.02, au=100.0),
        _lot(2, "5", wmt=3000.0, moisture=0.04, au=100.0),
    ]
    moist = estimate_moisture(lots)
    assert moist["005"] == pytest.approx(0.035, abs=1e-6)  # código normalizado


def test_humedad_solo_para_pilas_con_historia():
    lots = [_lot(1, "5", moisture=0.03, au=100.0)]
    moist = estimate_moisture(lots)
    assert "005" in moist and "999" not in moist


# --- Plan de rotación ----------------------------------------------------------- #
def _item(code, kg, au, ag=300.0, cu=0.15, pd=25.0):
    return InventoryItem(
        code=code, name=code, category=Category.RAEE, quantity_kg=kg,
        moisture=0.01, grade_cu=cu, grade_au=au, grade_ag=ag, grade_pd=pd,
    )


def test_rotacion_agota_el_stock_en_varios_envios():
    prices, terms = default_prices(), default_terms()
    items = [_item("A", 3000, au=120.0), _item("B", 3000, au=60.0)]
    plan = rotation_plan(items, prices, terms, container_kg=4000.0,
                         max_shipments=4, time_limit_s=4.0)
    assert len(plan.shipments) >= 2                    # no entra todo en uno
    assert plan.total_shipped_kg == pytest.approx(6000.0, abs=5.0)
    assert not plan.stuck                              # material rico: todo rota


def test_rotacion_detecta_pilas_estancadas():
    prices, terms = default_prices(), default_terms()
    # Una pila rica y una SIN valor (todo en cero): el optimizador nunca la sube.
    items = [_item("RICA", 2000, au=150.0),
             _item("MUERTA", 2000, au=0.0, ag=0.0, cu=0.0, pd=0.0)]
    plan = rotation_plan(items, prices, terms, container_kg=23000.0,
                         max_shipments=3, time_limit_s=4.0)
    assert "MUERTA" in plan.stuck
    assert plan.stuck["MUERTA"] == pytest.approx(2000.0, abs=1.0)
