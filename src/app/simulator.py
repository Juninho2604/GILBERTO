"""Punto de entrada de la app — Optimizador de Mezclas RAEE.

Interfaz en Python (Streamlit) con navegación por páginas:

- **Panel**         resumen ejecutivo: precisión del modelo y valor del optimizador.
- **Simulador**     arma una mezcla a mano y ve el resultado en vivo (Fase 1).
- **Optimizador**   el sistema arma las mezclas óptimas y explica por qué (Fase 2).
- **Histórico**     cada lote real vs. la mezcla óptima.
- **Caso de negocio** cuantifica el valor para fijarle precio al sistema.

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

from app.sidebar import render_sidebar
from app.ui import inject_css
from app.views import historico, negocio, optimizador, panel, simulador

st.set_page_config(
    page_title="Optimizador de Mezclas RAEE",
    page_icon="♻️",
    layout="wide",
    initial_sidebar_state="auto",  # se colapsa solo en celular; abierto en escritorio
)
inject_css()

# Barra lateral compartida (precios, términos, modo privado) — antes de navegar.
render_sidebar()

nav = st.navigation(
    [
        st.Page(panel.render, title="Panel", icon="📊", url_path="panel", default=True),
        st.Page(simulador.render, title="Simulador", icon="🧪", url_path="simulador"),
        st.Page(optimizador.render, title="Optimizador", icon="🎯", url_path="optimizador"),
        st.Page(historico.render, title="Histórico", icon="🗂️", url_path="historico"),
        st.Page(negocio.render, title="Caso de negocio", icon="💼", url_path="negocio"),
    ],
    position="top",  # pestañas horizontales arriba: siempre visibles (clave en celular)
)
nav.run()
