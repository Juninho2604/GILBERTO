"""Punto de entrada de la app — Optimizador de Mezclas RAEE.

Interfaz en Python (Streamlit) con un **panel de navegación propio** (no depende
del navegador ni de la barra lateral), siempre visible:

- **Panel**       resumen ejecutivo: precisión del modelo y valor del optimizador.
- **Inventario**  editar y cargar el stock en tiempo real (fuente de verdad).
- **Simulador**   arma una mezcla a mano y ve el resultado en vivo (Fase 1).
- **Optimizador** el sistema arma las mezclas óptimas y explica por qué (Fase 2).
- **Histórico**   cada lote real vs. la mezcla óptima, con el cálculo a la vista.

Ejecutar:  streamlit run src/app/simulator.py
"""

from __future__ import annotations

import sys
from pathlib import Path

# Permite importar los paquetes (``app``, ``domain``, ``data``…) al correr con
# `streamlit run src/app/simulator.py`.
SRC = Path(__file__).resolve().parents[1]
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

import streamlit as st

from app.auth import demo_mode, require_access
from app.sidebar import render_sidebar
from app.ui import inject_css, sidebar_account, sidebar_brand
from app.views import (
    demo,
    historico,
    inventario,
    optimizador,
    panel,
    simulador,
)

st.set_page_config(
    page_title="Aurix · Mezclas RAEE",
    page_icon="♻️",
    layout="wide",
    initial_sidebar_state="expanded",  # menú visible de entrada (también en celular)
)
inject_css()

# Portón de acceso: PIN en modo demo, contraseña (APP_PASSWORD) en modo normal.
require_access()

# --------------------------------------------------------------------------- #
# Navegación en el sidebar (estilo Aurix): marca + cuenta + ítems con ícono.
# --------------------------------------------------------------------------- #
if demo_mode():
    MODULES = {
        "Demo": ("smart_display", demo.render),
        "Inventario": ("inventory_2", inventario.render),
    }
else:
    MODULES = {
        "Demo": ("smart_display", demo.render),
        "Panel": ("dashboard", panel.render),
        "Inventario": ("inventory_2", inventario.render),
        "Simulador": ("science", simulador.render),
        "Optimizador": ("bolt", optimizador.render),
        "Histórico": ("history", historico.render),
    }
_OPTIONS = list(MODULES)
if st.session_state.get("nav_module") not in MODULES:
    st.session_state["nav_module"] = _OPTIONS[0]

# Marca + cuenta + parámetros en el sidebar (opcional, no afecta navegar).
sidebar_brand("Aurix")
sidebar_account("Servicios Megabytes", "Cuenta comercial", initials="SM")
if demo_mode():
    st.sidebar.caption(
        "Modo demo: solo Demo e Inventario. Para ver todos los módulos, quitá "
        "DEMO_MODE del .env y redeployá."
    )
render_sidebar()

# --------------------------------------------------------------------------- #
# Navegación SIEMPRE visible, ARRIBA (no depende del panel lateral).
# --------------------------------------------------------------------------- #
choice = st.pills(
    "Navegación", _OPTIONS,
    default=st.session_state["nav_module"],
    selection_mode="single", label_visibility="collapsed",
    width="stretch", key="nav_top",
)
if not choice:  # si se deselecciona, quedate en el módulo actual
    choice = st.session_state["nav_module"]
st.session_state["nav_module"] = choice
st.divider()
MODULES[choice][1]()
