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
from app.sidebar import render_settings
from app.ui import app_brand, inject_css, nav_bar
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
    initial_sidebar_state="collapsed",  # sin barra lateral: la navegación va en el cuerpo
)
inject_css()

# Portón de acceso: PIN en modo demo, contraseña (APP_PASSWORD) en modo normal.
require_access()

# --------------------------------------------------------------------------- #
# Módulos (ícono Material + función de render). En modo demo solo Demo +
# Inventario; en la app completa, los módulos reales (sin "Demo").
# --------------------------------------------------------------------------- #
if demo_mode():
    MODULES = {
        "Demo": ("smart_display", demo.render),
        "Inventario": ("inventory_2", inventario.render),
    }
else:
    MODULES = {
        "Panel": ("dashboard", panel.render),
        "Inventario": ("inventory_2", inventario.render),
        "Simulador": ("science", simulador.render),
        "Optimizador": ("bolt", optimizador.render),
        "Histórico": ("history", historico.render),
    }
_OPTIONS = list(MODULES)
_ICONS = {name: icon for name, (icon, _) in MODULES.items()}
if st.session_state.get("nav_module") not in MODULES:
    st.session_state["nav_module"] = _OPTIONS[0]

# --------------------------------------------------------------------------- #
# Encabezado: marca a la izquierda, "Ajustes" (popover) a la derecha. Todo en el
# cuerpo — sin barra lateral, así la navegación nunca se "pierde" al ocultar nada.
# --------------------------------------------------------------------------- #
head_l, head_r = st.columns([4, 1], vertical_alignment="center")
with head_l:
    app_brand("Aurix", "Optimizador de Mezclas RAEE · Servicios Megabytes")
with head_r:
    render_settings()  # deja prices/terms/z_min/k_safe en session_state

st.write("")

# Barra de módulos: SIEMPRE visible en el cuerpo, el activo en verde.
choice = nav_bar(_OPTIONS, _ICONS)
st.divider()
MODULES[choice][1]()
