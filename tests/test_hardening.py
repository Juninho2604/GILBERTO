"""Tests del endurecimiento v1.1: lockout de login, ledger persistente, fallback."""

import json

import pytest

from app import auth
from data import bootstrap, ledger_store


# --- Lockout de login (anti fuerza bruta) ---------------------------------- #
@pytest.fixture(autouse=True)
def _reset_lock():
    auth._LOCK["failures"] = 0
    auth._LOCK["until"] = 0.0
    yield
    auth._LOCK["failures"] = 0
    auth._LOCK["until"] = 0.0


def test_contrasena_correcta_pasa():
    assert auth._check_secret("abc", "abc", "test") is True
    assert auth._locked_remaining_s() == 0


def test_fallos_repetidos_bloquean():
    for _ in range(auth._MAX_ATTEMPTS):
        assert auth._check_secret("mala", "buena", "test") is False
    assert auth._locked_remaining_s() > 0


def test_bloqueado_rechaza_incluso_la_correcta():
    for _ in range(auth._MAX_ATTEMPTS):
        auth._check_secret("mala", "buena", "test")
    # Con el lockout activo, ni la contraseña correcta pasa.
    assert auth._check_secret("buena", "buena", "test") is False


def test_exito_resetea_el_contador():
    for _ in range(auth._MAX_ATTEMPTS - 1):
        auth._check_secret("mala", "buena", "test")
    assert auth._check_secret("buena", "buena", "test") is True
    # Tras el éxito, los fallos anteriores no cuentan.
    assert auth._LOCK["failures"] == 0
    assert auth._locked_remaining_s() == 0


# --- Ledger del bono persistente -------------------------------------------- #
def test_ledger_roundtrip(tmp_path):
    path = tmp_path / "ledger.json"
    assert ledger_store.load_ledger(path) == []
    ledger_store.append_entry(3212.0, 482.0, 0.20, path=path)
    ledger_store.append_entry(1500.0, 225.0, 0.15, path=path)
    entries = ledger_store.load_ledger(path)
    assert len(entries) == 2
    assert entries[0]["n"] == 1 and entries[1]["n"] == 2
    assert entries[0]["rescatado_usd"] == 3212.0
    assert entries[0]["bono_usd"] == 482.0
    assert entries[0]["timestamp"]  # queda fechado
    assert entries[0]["estado"] == "registrado"


def test_ledger_sobrevive_recarga_desde_disco(tmp_path):
    path = tmp_path / "ledger.json"
    ledger_store.append_entry(100.0, 15.0, 0.12, path=path)
    # "Reinicio del servidor": se relee desde disco, no de la memoria.
    assert len(ledger_store.load_ledger(path)) == 1


def test_ledger_archivo_corrupto_no_crashea(tmp_path):
    path = tmp_path / "ledger.json"
    path.write_text("{esto no es json", encoding="utf-8")
    assert ledger_store.load_ledger(path) == []


def test_ledger_clear(tmp_path):
    path = tmp_path / "ledger.json"
    ledger_store.append_entry(100.0, 15.0, 0.12, path=path)
    ledger_store.clear_ledger(path)
    assert ledger_store.load_ledger(path) == []
    assert not path.exists()


def test_ledger_escritura_atomica(tmp_path):
    # El tmp intermedio no debe quedar tirado tras escribir.
    path = tmp_path / "ledger.json"
    ledger_store.append_entry(100.0, 15.0, 0.12, path=path)
    assert not path.with_suffix(".json.tmp").exists()
    assert json.loads(path.read_text(encoding="utf-8"))["entries"]


# --- Fallback a datos de ejemplo: detectado y marcado ------------------------ #
def test_fallback_marca_flag(monkeypatch):
    import data.load_inventory as li

    def _boom(**kwargs):
        raise FileNotFoundError("inventory.xlsx no está")

    monkeypatch.setattr(li, "load_raee_inventory", _boom)
    items = bootstrap.default_inventory()
    assert bootstrap.LAST_LOAD_FALLBACK is True
    assert items  # el fallback devuelve el inventario de ejemplo


def test_carga_real_no_marca_flag():
    items = bootstrap.default_inventory()
    assert bootstrap.LAST_LOAD_FALLBACK is False
    assert items
