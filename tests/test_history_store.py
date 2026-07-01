"""Tests del loop de datos (v1.2): cargar liquidaciones nuevas desde la app."""

import pytest

from data.estimate_grades import estimate_grades
from data.history_store import append_lot, count_extra, extra_lots, validate_lot
from data.ledger_store import append_entry, load_ledger, reconcile_entry
from data.load_history import load_history


def _lot(**over):
    d = {
        "customer_lot": "95i",
        "jx_lot": "9999",
        "wmt": 5200.0,
        "moisture": 0.012,
        "grades": {"CU": 0.19, "AU": 92.0, "AG": 610.0, "PT": 0.0, "PD": 21.0},
        "recipe_raw": "1*(30%) + 2*(70%)",
    }
    d.update(over)
    return d


# --- Validación ------------------------------------------------------------- #
def test_lote_valido_pasa():
    assert validate_lot(_lot()) == []


def test_rechaza_peso_cero_y_sin_leyes():
    errs = validate_lot(_lot(wmt=0, grades={}))
    assert any("WMT" in e for e in errs)
    assert any("al menos una ley" in e for e in errs)


def test_rechaza_jx_duplicado():
    errs = validate_lot(_lot(jx_lot="123"), existing_jx={"123"})
    assert any("duplicado" in e for e in errs)


# --- Persistencia y fusión con el histórico ---------------------------------- #
def test_append_y_extra_lots_roundtrip(tmp_path):
    path = tmp_path / "extra.json"
    append_lot(_lot(), path=path)
    assert count_extra(path) == 1
    lots = extra_lots(path)
    assert len(lots) == 1
    L = lots[0]
    assert L.customer_lot == "95i"
    assert L.wmt == 5200.0
    assert abs(L.dmt - 5200.0 * (1 - 0.012)) < 1e-6  # DMT derivado
    assert L.grades["AU"] == 92.0
    assert L.recipe.resolvable  # la receta se parsea al cargar


def test_load_history_fusiona_extras(tmp_path):
    path = tmp_path / "extra.json"
    base = len(load_history(include_extra=False))
    append_lot(_lot(), path=path)
    merged = load_history(extra_path=path)
    assert len(merged) == base + 1
    assert str(merged[-1].customer_lot) == "95i"


def test_liquidacion_nueva_afina_las_leyes(tmp_path):
    """El corazón del "se afina solo": un lote PURO nuevo de una pila
    desconocida crea su estimación de ley al fusionarse con el histórico."""
    path = tmp_path / "extra.json"
    append_lot(_lot(customer_lot="96i", jx_lot="9998", recipe_raw="777",
                    grades={"CU": 0.10, "AU": 55.0, "AG": 300.0, "PT": 0.0,
                            "PD": 25.0}), path=path)
    est = estimate_grades(load_history(extra_path=path))
    assert "777" in est                      # la pila nueva ahora tiene ley
    assert est["777"].grades["AU"] == pytest.approx(55.0)


# --- Reconciliación del bono -------------------------------------------------- #
def test_reconciliar_envio_del_ledger(tmp_path):
    path = tmp_path / "ledger.json"
    append_entry(3212.0, 482.0, 0.20, path=path)
    reconcile_entry(1, 70335.68, path=path)
    e = load_ledger(path)[0]
    assert e["estado"] == "reconciliado"
    assert e["real_usd"] == 70335.68
    assert e["reconciled_at"]
