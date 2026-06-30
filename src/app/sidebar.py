"""Ajustes del motor (precios, términos del contrato y riesgo).

Se muestran en un **popover "Ajustes"** dentro del encabezado, en el cuerpo de la
página — **no** en una barra lateral, para que nunca quede una navegación
"atrapada" al ocultar el panel. Deja ``prices``, ``terms``, ``z_min`` y
``k_safe`` en ``st.session_state`` para que cada vista los consuma.
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


def _ensure_defaults() -> None:
    st.session_state.setdefault("prices", default_prices())
    st.session_state.setdefault("terms", default_terms())
    st.session_state.setdefault("private", False)
    st.session_state.setdefault("z_min", 1.5)
    st.session_state.setdefault("k_safe", 1.0)
    # Bono de éxito (§4 del change-order).
    st.session_state.setdefault("umbral_mejora", 0.10)
    st.session_state.setdefault("tasa_bono", 0.15)
    st.session_state.setdefault("ventana_envios", 1)


def render_settings() -> tuple[MetalPrices, ContractTerms, bool]:
    """Popover de ajustes en el encabezado. Devuelve (prices, terms, private)."""
    from app.auth import demo_mode

    _ensure_defaults()

    # En modo demo: defaults silenciosos, sin parámetros a la vista.
    if demo_mode():
        st.session_state.prices = default_prices()
        st.session_state.terms = default_terms()
        st.session_state.private = False
        st.session_state.z_min = 1.5
        st.session_state.k_safe = 1.0
        return st.session_state.prices, st.session_state.terms, False

    p: MetalPrices = st.session_state.prices
    t: ContractTerms = st.session_state.terms

    with st.popover("Ajustes", icon=":material/tune:", use_container_width=True):
        st.caption(
            "Precios del día, términos del contrato y riesgo. Las pilas se "
            "muestran siempre solo por **código** (sin nombres)."
        )
        tab_p, tab_c, tab_r, tab_b = st.tabs(
            ["Precios", "Contrato y RR", "Riesgo", "Bono"]
        )

        with tab_p:
            st.caption("Cu en USD/t · preciosos en USD/onza troy (referencia §10).")
            c1, c2 = st.columns(2)
            price_cu = c1.number_input("Cu (USD/t)", value=float(p.price_cu), step=10.0, format="%.2f")
            price_au = c2.number_input("Au (USD/oz)", value=float(p.price_au), step=10.0, format="%.2f")
            price_ag = c1.number_input("Ag (USD/oz)", value=float(p.price_ag), step=0.5, format="%.2f")
            price_pt = c2.number_input("Pt (USD/oz)", value=float(p.price_pt), step=10.0, format="%.2f")
            price_pd = c1.number_input("Pd (USD/oz)", value=float(p.price_pd), step=10.0, format="%.2f")
        prices = MetalPrices(price_cu, price_au, price_ag, price_pt, price_pd)

        with tab_c:
            st.caption("Refining charges (RC), cargos y deducciones — CONFIRMAR (§7).")
            c1, c2 = st.columns(2)
            rc_cu = c1.number_input("RC Cu (USD/t)", value=float(t.rc_cu), step=10.0, format="%.2f")
            rc_au = c2.number_input("RC Au (USD/oz)", value=float(t.rc_au), step=0.5, format="%.2f")
            rc_ag = c1.number_input("RC Ag (USD/oz)", value=float(t.rc_ag), step=0.1, format="%.2f")
            rc_pd = c2.number_input("RC Pd (USD/oz)", value=float(t.rc_pd), step=0.5, format="%.2f")
            tc_rate = c1.number_input("Treatment (USD/Dt)", value=float(t.tc_rate), step=10.0, format="%.2f")
            shred_rate = c2.number_input("Shredding (USD/t)", value=float(t.shred_rate), step=10.0, format="%.2f")
            st.divider()
            cu_ded = c1.number_input("Cu: deducción", value=float(t.cu_deduction), step=0.01, format="%.3f")
            au_ded = c2.number_input("Au: deducción (g/t)", value=float(t.au_rule.deduction), step=1.0, format="%.1f")
            au_cap = c1.number_input("Au: tope RR", value=float(t.au_rule.cap or 0.96), step=0.01, format="%.2f")
            ag_ded = c2.number_input("Ag: deducción (g/t)", value=float(t.ag_rule.deduction), step=1.0, format="%.1f")
            ag_cap = c1.number_input("Ag: tope RR", value=float(t.ag_rule.cap or 0.95), step=0.01, format="%.2f")
            pd_ded = c2.number_input("Pd: deducción (g/t)", value=float(t.pd_rule.deduction), step=1.0, format="%.1f")
            pt_paid = st.checkbox("Pt se paga", value=t.pt_rule.paid)

        with tab_r:
            st.caption("Cuán seguro debe ser el cobro de cada metal (margen en σ).")
            z_min = st.number_input(
                "z mínimo (margen en σ)", value=float(st.session_state.get("z_min", 1.5)),
                step=0.1, format="%.1f",
                help="Margen mínimo sobre el umbral, en desviaciones estándar. 1.5 "
                "≈ 93% de probabilidad de cobro. Más alto = más conservador.",
            )
            k_safe = st.number_input(
                "k (ley conservadora)", value=float(st.session_state.get("k_safe", 1.0)),
                step=0.5, format="%.1f",
                help="Cuántas σ se descuentan para valorizar conservador (grade − k·σ).",
            )

        with tab_b:
            st.caption("Bono de éxito: umbral de mejora, tasa y ventana de envíos.")
            umbral_mejora = st.number_input(
                "Umbral de mejora", value=float(st.session_state.get("umbral_mejora", 0.10)),
                min_value=0.0, step=0.01, format="%.2f",
                help="Mejora mínima de un envío real para activar el bono. 0.10 = "
                "10% (piso de ruido del ensayo).",
            )
            tasa_bono = st.number_input(
                "Tasa del bono", value=float(st.session_state.get("tasa_bono", 0.15)),
                min_value=0.0, step=0.01, format="%.2f",
                help="Fracción del sub-pago histórico que se paga como bono. 0.15 = 15%.",
            )
            ventana_envios = st.number_input(
                "Ventana de envíos", value=int(st.session_state.get("ventana_envios", 1)),
                min_value=1, step=1, format="%d",
                help="Cuántos envíos reales (promediados) se usan para medir la "
                "mejora. Más envíos = disparador más robusto al ruido.",
            )

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

    st.session_state.prices = prices
    st.session_state.terms = terms
    st.session_state.private = False
    st.session_state.z_min = z_min
    st.session_state.k_safe = k_safe
    st.session_state.umbral_mejora = umbral_mejora
    st.session_state.tasa_bono = tasa_bono
    st.session_state.ventana_envios = int(ventana_envios)
    return prices, terms, False


# Compatibilidad: nombre anterior.
render_sidebar = render_settings
