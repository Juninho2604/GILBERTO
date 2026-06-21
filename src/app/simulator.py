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

from app.auth import require_login
from app.sidebar import render_sidebar
from app.ui import inject_css
from app.views import (
    demo,
    historico,
    inventario,
    optimizador,
    panel,
    simulador,
)

st.set_page_config(
    page_title="Optimizador de Mezclas RAEE",
    page_icon="♻️",
    layout="wide",
    initial_sidebar_state="auto",  # se colapsa solo en celular; abierto en escritorio
)
inject_css()

# Portón de acceso: exige contraseña (APP_PASSWORD) antes de mostrar nada.
require_login()

# Barra lateral compartida (precios, términos, modo privado).
render_sidebar()

# --------------------------------------------------------------------------- #
# Panel de navegación propio (pills): siempre visible, ideal para celular.
# --------------------------------------------------------------------------- #
MODULES = {
    "Demo": ("🎬", demo.render),
    "Panel": ("📊", panel.render),
    "Inventario": ("📦", inventario.render),
    "Simulador": ("🧪", simulador.render),
    "Optimizador": ("🎯", optimizador.render),
    "Histórico": ("🗂️", historico.render),
}
_OPTIONS = list(MODULES)

choice = st.pills(
    "Navegación",
    _OPTIONS,
    default=_OPTIONS[0],
    selection_mode="single",
    format_func=lambda k: f"{MODULES[k][0]} {k}",
    key="nav_module",
    label_visibility="collapsed",
    width="stretch",
)
if not choice:  # si se deselecciona, quedate en el módulo actual
    choice = st.session_state.get("_last_module", _OPTIONS[0])
st.session_state["_last_module"] = choice

st.divider()
MODULES[choice][1]()
