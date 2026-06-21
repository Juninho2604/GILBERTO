"""Tests del portón de acceso (login básico por contraseña)."""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

AppTest = pytest.importorskip("streamlit.testing.v1").AppTest

_APP = '''
import sys; sys.path.insert(0, "src")
import streamlit as st
from app.auth import require_login
require_login()
st.write("CONTENIDO_SECRETO")
'''


def _secret_visible(at) -> bool:
    return any("CONTENIDO_SECRETO" in (m.value or "") for m in at.markdown)


def test_gate_blocks_without_login(monkeypatch):
    monkeypatch.setenv("APP_PASSWORD", "clave-secreta")
    at = AppTest.from_string(_APP, default_timeout=60).run()
    assert not _secret_visible(at)          # contenido oculto
    assert len(at.text_input) == 1          # pide contraseña


def test_gate_rejects_wrong_password(monkeypatch):
    monkeypatch.setenv("APP_PASSWORD", "clave-secreta")
    at = AppTest.from_string(_APP, default_timeout=60).run()
    at.text_input[0].set_value("incorrecta")
    at.button[0].click().run()
    assert not _secret_visible(at)
    assert len(at.error) > 0


def test_gate_allows_correct_password(monkeypatch):
    monkeypatch.setenv("APP_PASSWORD", "clave-secreta")
    at = AppTest.from_string(_APP, default_timeout=60).run()
    at.text_input[0].set_value("clave-secreta")
    at.button[0].click().run()
    assert _secret_visible(at)


def test_no_password_warns_but_allows(monkeypatch):
    monkeypatch.delenv("APP_PASSWORD", raising=False)
    at = AppTest.from_string(_APP, default_timeout=60).run()
    assert _secret_visible(at)              # no bloquea (dev local)
    assert len(at.warning) > 0              # pero avisa
