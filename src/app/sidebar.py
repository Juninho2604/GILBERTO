"""Barra lateral compartida: precios, términos del contrato y modo privado.

Se renderiza en todas las páginas y deja ``prices``, ``terms`` y ``private`` en
``st.session_state`` para que cada vista los consuma.
"""

from __future__ import annotations

import streamlit as st

from domain.models import (
    ContractTerms,
    MetalPrices,
    RecoveryRule,
    default_prices,
    default_terms,
)


def render_sidebar() -> tuple[MetalPrices, ContractTerms, bool]:
    from app.auth import demo_mode

    if "prices" not in st.session_state:
        st.session_state.prices = default_prices()
    if "terms" not in st.session_state:
        st.session_state.terms = default_terms()

    # En modo demo: sin parámetros del motor a la vista (defaults silenciosos).
    if demo_mode():
        st.session_state.prices = default_prices()
        st.session_state.terms = default_terms()
        st.session_state.private = False
        st.session_state.z_min = 1.5
        st.session_state.k_safe = 1.0
        st.sidebar.markdown("### Servicios Megabytes, C.A.")
        st.sidebar.caption("Optimizador de Mezclas RAEE · demo")
        return st.session_state.prices, st.session_state.terms, False

    p: MetalPrices = st.session_state.prices
    t: ContractTerms = st.session_state.terms

    st.sidebar.markdown("### ⚙️ Parámetros")
    # Privacidad: las pilas se muestran SIEMPRE solo por su código asignado.
    # Nunca el nombre del material (protección de info de Gilberto y su socio).
    private = False
    st.sidebar.caption("🔒 Las pilas se muestran solo por **código** (sin nombres).")

    with st.sidebar.expander("💲 Precios del día", expanded=False):
        st.caption("Cu en USD/t · preciosos en USD/onza troy (referencia §10).")
        price_cu = st.number_input("Cu (USD/t)", value=float(p.price_cu), step=10.0, format="%.2f")
        price_au = st.number_input("Au (USD/oz)", value=float(p.price_au), step=10.0, format="%.2f")
        price_ag = st.number_input("Ag (USD/oz)", value=float(p.price_ag), step=0.5, format="%.2f")
        price_pt = st.number_input("Pt (USD/oz)", value=float(p.price_pt), step=10.0, format="%.2f")
        price_pd = st.number_input("Pd (USD/oz)", value=float(p.price_pd), step=10.0, format="%.2f")
    prices = MetalPrices(price_cu, price_au, price_ag, price_pt, price_pd)

    with st.sidebar.expander("📄 Términos del contrato", expanded=False):
        st.caption("Refining charges (RC) y cargos de procesamiento.")
        rc_cu = st.number_input("RC Cu (USD/t)", value=float(t.rc_cu), step=10.0, format="%.2f")
        rc_au = st.number_input("RC Au (USD/oz)", value=float(t.rc_au), step=0.5, format="%.2f")
        rc_ag = st.number_input("RC Ag (USD/oz)", value=float(t.rc_ag), step=0.1, format="%.2f")
        rc_pd = st.number_input("RC Pd (USD/oz)", value=float(t.rc_pd), step=0.5, format="%.2f")
        tc_rate = st.number_input("Treatment (USD/Dt)", value=float(t.tc_rate), step=10.0, format="%.2f")
        shred_rate = st.number_input("Shredding (USD/t)", value=float(t.shred_rate), step=10.0, format="%.2f")

    with st.sidebar.expander("🧮 Deducciones y topes (RR)", expanded=False):
        st.caption("Términos de recuperación — CONFIRMAR con Gilberto (§7).")
        cu_ded = st.number_input("Cu: deducción", value=float(t.cu_deduction), step=0.01, format="%.3f")
        au_ded = st.number_input("Au: deducción (g/t)", value=float(t.au_rule.deduction), step=1.0, format="%.1f")
        au_cap = st.number_input("Au: tope RR", value=float(t.au_rule.cap or 0.96), step=0.01, format="%.2f")
        ag_ded = st.number_input("Ag: deducción (g/t)", value=float(t.ag_rule.deduction), step=1.0, format="%.1f")
        ag_cap = st.number_input("Ag: tope RR", value=float(t.ag_rule.cap or 0.95), step=0.01, format="%.2f")
        pd_ded = st.number_input("Pd: deducción (g/t)", value=float(t.pd_rule.deduction), step=1.0, format="%.1f")
        pt_paid = st.checkbox("Pt se paga", value=t.pt_rule.paid)

    terms = ContractTerms(
        rc_cu=rc_cu, rc_au=rc_au, rc_ag=rc_ag, rc_pt=t.rc_pt, rc_pd=rc_pd,
        cu_deduction=cu_ded,
        au_rule=RecoveryRule(deduction=au_ded, cap=au_cap),
        ag_rule=RecoveryRule(deduction=ag_ded, cap=ag_cap, floor_zero=True),
        pd_rule=RecoveryRule(deduction=pd_ded, cap=None, floor_zero=True),
        pt_rule=RecoveryRule(deduction=0.0, paid=pt_paid, floor_zero=True),
        tc_rate=tc_rate, shred_rate=shred_rate,
        min_lot_charge=t.min_lot_charge, moisture_penalty=t.moisture_penalty,
    )

    with st.sidebar.expander("🎯 Riesgo de umbral", expanded=False):
        st.caption("Cuán seguro debe ser el cobro de cada metal (margen en σ).")
        z_min = st.number_input(
            "z mínimo (margen en σ)", value=1.5, step=0.1, format="%.1f",
            help="Margen mínimo sobre el umbral, en desviaciones estándar. 1.5 ≈ "
            "93% de probabilidad de cobro. Más alto = más conservador.",
        )
        k_safe = st.number_input(
            "k (ley conservadora)", value=1.0, step=0.5, format="%.1f",
            help="Cuántas σ se descuentan para valorizar conservador (grade − k·σ).",
        )

    st.session_state.prices = prices
    st.session_state.terms = terms
    st.session_state.private = private
    st.session_state.z_min = z_min
    st.session_state.k_safe = k_safe

    st.sidebar.markdown("---")
    st.sidebar.caption(
        "Servicios Megabytes, C.A. · Optimizador de Mezclas RAEE. "
        "Leyes **estimadas** desde el histórico (a validar con laboratorio)."
    )
    return prices, terms, private
