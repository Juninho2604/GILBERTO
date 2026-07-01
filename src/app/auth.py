"""Login básico por contraseña para proteger la app en un deploy público.

La contraseña esperada sale de la variable de entorno ``APP_PASSWORD`` (un
secreto, nunca en el repo) o de ``st.secrets``. Si está configurada, se exige
antes de mostrar cualquier dato. Si no, se permite el acceso pero con un aviso
visible (para no bloquear el desarrollo local).

⚠️ Esto es un **portón básico**, no gestión de usuarios. Sobre HTTP la
contraseña viaja en texto plano: para protección real, poné un proxy con HTTPS
(Caddy/nginx) delante del :8501.
"""

from __future__ import annotations

import hmac
import os
import time

import streamlit as st

from applog import get_logger

_LOG = get_logger("aurix.auth")

# ---------------------------------------------------------------------------
# Límite de intentos (anti fuerza bruta). Estado a nivel PROCESO, no sesión:
# abrir sesiones nuevas no resetea el contador. Tras _MAX_ATTEMPTS fallos, el
# login queda bloqueado _LOCK_SECONDS para todos (trade-off aceptado: un
# atacante puede molestar 5 min, pero no adivinar un PIN de 4 dígitos).
# ---------------------------------------------------------------------------
_MAX_ATTEMPTS = 5
_LOCK_SECONDS = 300.0
_LOCK = {"failures": 0, "until": 0.0}


def _locked_remaining_s() -> int:
    """Segundos que faltan para desbloquear el login (0 = desbloqueado)."""
    return max(0, int(_LOCK["until"] - time.time()))


def _register_failure(kind: str) -> None:
    _LOCK["failures"] += 1
    _LOG.warning("Intento de %s fallido (%d/%d).", kind, _LOCK["failures"], _MAX_ATTEMPTS)
    if _LOCK["failures"] >= _MAX_ATTEMPTS:
        _LOCK["until"] = time.time() + _LOCK_SECONDS
        _LOCK["failures"] = 0
        _LOG.warning("Login bloqueado por %d s (demasiados intentos).", int(_LOCK_SECONDS))


def _register_success() -> None:
    _LOCK["failures"] = 0
    _LOCK["until"] = 0.0


def _check_secret(entered: str, expected: str, kind: str) -> bool:
    """Compara en tiempo constante, con límite de intentos. True si pasa."""
    if _locked_remaining_s() > 0:
        return False
    if hmac.compare_digest(str(entered), str(expected)):
        _register_success()
        return True
    _register_failure(kind)
    return False


def _lockout_error() -> None:
    mins = max(1, -(-_locked_remaining_s() // 60))  # ceil
    st.error(
        f"Demasiados intentos fallidos. Probá de nuevo en ~{mins} minuto(s).",
        icon=":material/lock_clock:",
    )


def _expected_password() -> str | None:
    """Contraseña configurada (env var o secrets), o None si no hay."""
    pw = os.environ.get("APP_PASSWORD")
    if pw:
        return pw
    try:
        return st.secrets.get("APP_PASSWORD")  # type: ignore[no-any-return]
    except Exception:
        return None


def demo_mode() -> bool:
    """Modo demo (para reuniones): solo Inventario + Demo, con PIN."""
    return os.environ.get("DEMO_MODE", "") == "1"


def _expected_pin() -> str | None:
    pin = os.environ.get("DEMO_PIN")
    if pin:
        return pin
    try:
        return st.secrets.get("DEMO_PIN")  # type: ignore[no-any-return]
    except Exception:
        return None


def require_access() -> None:
    """Portón de entrada: PIN en modo demo, contraseña en modo normal."""
    if demo_mode() and _expected_pin():
        if st.session_state.get("_pin_ok"):
            return
        _render_pin(_expected_pin())
        st.stop()
    require_login()


def _render_pin(expected: str) -> None:
    st.markdown("<div style='height:10vh'></div>", unsafe_allow_html=True)
    _, mid, _ = st.columns([1, 1, 1])
    with mid:
        st.markdown(
            "<div class='brand' style='justify-content:center'>"
            "<span class='dot'></span><span class='title'>Acceso</span></div>",
            unsafe_allow_html=True,
        )
        st.markdown(
            "<div class='subtle' style='text-align:center;margin-bottom:1rem'>"
            "Ingresá tu PIN para continuar.</div>",
            unsafe_allow_html=True,
        )
        with st.form("pin", clear_on_submit=True):
            pin = st.text_input("PIN", type="password", label_visibility="collapsed",
                                placeholder="• • • •")
            ok = st.form_submit_button("Entrar", type="primary", width="stretch")
        if ok:
            if _locked_remaining_s() > 0:
                _lockout_error()
            elif _check_secret(pin, expected, "PIN"):
                st.session_state["_pin_ok"] = True
                st.rerun()
            elif _locked_remaining_s() > 0:
                _lockout_error()  # este fallo activó el bloqueo: avisar ya
            else:
                st.error("PIN incorrecto.")


def require_login() -> None:
    """Exige contraseña antes de renderizar la app. Llamar al inicio del entrypoint."""
    expected = _expected_password()

    if not expected:
        # Sin contraseña configurada: no bloquear (dev), pero avisar fuerte.
        st.warning(
            "**App sin contraseña.** Configurá `APP_PASSWORD` para proteger el "
            "inventario y la fórmula en un acceso público.",
            icon=":material/lock_open:",
        )
        return

    if st.session_state.get("_auth_ok"):
        return

    _render_login(expected)
    st.stop()


def _render_login(expected: str) -> None:
    st.markdown("<div style='height:8vh'></div>", unsafe_allow_html=True)
    _, mid, _ = st.columns([1, 1.1, 1])
    with mid:
        st.markdown(
            "<div class='brand' style='justify-content:center'>"
            "<span class='dot'></span><span class='title'>Acceso privado</span></div>",
            unsafe_allow_html=True,
        )
        st.markdown(
            "<div class='subtle' style='text-align:center;margin-bottom:1rem'>"
            "Optimizador de Mezclas RAEE · Servicios Megabytes, C.A.</div>",
            unsafe_allow_html=True,
        )
        with st.form("login", clear_on_submit=False):
            pwd = st.text_input("Contraseña", type="password", label_visibility="collapsed",
                                placeholder="Contraseña")
            ok = st.form_submit_button("Entrar", type="primary", width="stretch")
        if ok:
            if _locked_remaining_s() > 0:
                _lockout_error()
            elif _check_secret(pwd, expected, "contraseña"):
                st.session_state["_auth_ok"] = True
                st.rerun()
            elif _locked_remaining_s() > 0:
                _lockout_error()  # este fallo activó el bloqueo: avisar ya
            else:
                st.error("Contraseña incorrecta.")
        st.caption("Datos comerciales confidenciales. Acceso solo autorizado.")
