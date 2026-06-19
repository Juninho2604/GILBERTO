"""Tests de carga de datos y estimación de leyes (secciones 6 y 9).

Dependen de los ``.xlsx`` reales en ``data/``. Si no están, se omiten.
"""

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from data.load_inventory import DEFAULT_INVENTORY_XLSX, load_inventory, load_raee_inventory
from data.load_history import DEFAULT_HISTORY_XLSX, load_history
from data.estimate_grades import Confidence, estimate_grades, reconstruction_report
from domain.models import Category

pytestmark = pytest.mark.skipif(
    not DEFAULT_INVENTORY_XLSX.exists() or not DEFAULT_HISTORY_XLSX.exists(),
    reason="faltan los .xlsx reales en data/",
)


def test_inventory_counts():
    items = load_inventory()
    raee = [i for i in items if i.category == Category.RAEE]
    with_stock = load_raee_inventory(with_stock_only=True)
    # El brief indica 40 ítems RAEE con stock.
    assert len(with_stock) == 40
    assert all(i.category == Category.RAEE for i in raee)
    # El mayor volumen es Bajo Grado Marrón (~13.330 kg).
    top = max(with_stock, key=lambda i: i.quantity_kg)
    assert top.code == "001"
    assert top.quantity_kg == pytest.approx(13_329.97, abs=1)


def test_history_loads_53_lots():
    lots = load_history()
    assert len(lots) == 53
    first = lots[0]
    assert first.wmt == pytest.approx(5184.0)
    assert first.moisture == pytest.approx(0.009)
    assert first.grades["AU"] == pytest.approx(84.4)


def test_estimation_covers_25_of_40():
    inv = load_raee_inventory(with_stock_only=True)
    names = {it.code: it.name for it in inv}
    est = estimate_grades(load_history(), names=names)
    stocked = {it.code for it in inv}
    covered = stocked & set(est)
    # El brief estima 25 de 40 cubiertas, 15 pendientes.
    assert len(covered) == 25


def test_pure_lots_marked_direct():
    est = estimate_grades(load_history())
    # 009 (Boards Tipo 1) aparece en lotes puros → medición directa.
    assert est["009"].confidence == Confidence.DIRECT
    assert est["009"].n_pure_lots >= 1
    assert est["009"].grades["AU"] > 0


def test_reconstruction_error_reasonable():
    rep = reconstruction_report()
    assert len(rep) == 36  # recetas resolubles
    # El error mediano de Au sobre lotes resolubles debe ser chico (< 15%).
    au_errs = sorted(abs(r["AU_err%"]) for r in rep if r["AU_actual"] > 0)
    median = au_errs[len(au_errs) // 2]
    assert median < 15.0
