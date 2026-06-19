"""Optimizador — el sistema arma las mezclas óptimas y explica por qué (Fase 2)."""

from __future__ import annotations

import streamlit as st

from analysis.explain import explain_partition
from app.data_access import inventory_items
from app.ui import brand, usd, usd2
from app.views.components import (
    components_table,
    explanation_block,
    lot_header_metrics,
    metal_table,
)
from domain.valuation import BlendComponent, value_blend
from optimize.optimizer import optimize_partition

_ROLE_LABEL = {"rico": "LOTE RICO", "relleno": "RELLENO", "mixto": "MIXTO"}


def render() -> None:
    prices = st.session_state.prices
    terms = st.session_state.terms
    private = st.session_state.get("private", False)

    brand(
        "Optimizador de mezclas",
        "Reparte el inventario en lotes para que la refinería pague lo máximo.",
    )
    st.write("")

    items = inventory_items()

    c1, c2, c3 = st.columns([1, 1, 1])
    num_lots = c1.slider("Cantidad de lotes", 1, 4, 2)
    min_lot_kg = c2.number_input("Tamaño mínimo por lote (kg)", value=0.0, step=100.0)
    run = c3.button("▶ Optimizar", type="primary", width="stretch")

    st.caption(
        "Clave del modelo: **no diluir** las pilas ricas en oro con relleno pobre, "
        "porque la deducción de 7 g/t de Au se aplica sobre toda la masa del lote."
    )

    if not run and "opt_result" not in st.session_state:
        st.info("Ajustá los parámetros y tocá **Optimizar**.")
        return

    if run:
        with st.spinner("Resolviendo el modelo (MILP)…"):
            res = optimize_partition(
                items, prices, terms, num_lots=num_lots, min_lot_kg=min_lot_kg
            )
            # Alternativa ingenua: el mismo material en una sola mezcla.
            single = value_blend(
                [BlendComponent(it, it.quantity_kg) for it in items], prices, terms
            )
            expl = explain_partition([l.valuation for l in res.lots], single, terms)
        st.session_state.opt_result = res
        st.session_state.opt_expl = expl.to_dict()

    res = st.session_state.opt_result
    expl = st.session_state.opt_expl
    if not res.lots:
        st.warning(f"Sin solución (status={res.status}).")
        return

    # --- Titular ---------------------------------------------------------- #
    st.markdown(f"### {usd2(res.net_value_usd)}")
    st.markdown(expl["headline"])
    st.write("")

    # --- Por qué es la mejor decisión ------------------------------------- #
    st.markdown("##### Por qué es la mejor decisión")
    explanation_block(expl)
    st.write("")

    # --- Detalle de cada lote --------------------------------------------- #
    st.markdown("##### Lotes propuestos")
    for i, lot in enumerate(res.lots, 1):
        v = lot.valuation
        role = expl["lots"][i - 1]["role"] if i - 1 < len(expl["lots"]) else "mixto"
        with st.expander(
            f"Lote {i} · {_ROLE_LABEL.get(role, '')} — {usd(v.net_value_usd)} · "
            f"{v.result_per_kg:.1f} USD/kg · {lot.total_weight_kg:,.0f} kg · "
            f"Au {v.metals['AU'].grade:.0f} g/t",
            expanded=(i == 1),
        ):
            lot_header_metrics(v)
            st.write("")
            comp_rows = [
                {
                    "code": p.item.code,
                    "name": p.item.name,
                    "kg": round(p.weight_kg, 1),
                    "grade_au": round(p.item.grade_au, 1),
                    "grade_ag": round(p.item.grade_ag, 0),
                    "grade_cu": round(p.item.grade_cu, 4),
                    "grade_pd": round(p.item.grade_pd, 1),
                }
                for p in lot.components
            ]
            cc1, cc2 = st.columns([1, 1])
            with cc1:
                st.caption("Pilas del lote")
                components_table(comp_rows, private)
            with cc2:
                metal_table(v)

    if res.leftover:
        from app.ui import pile_label

        names = {it.code: it.name for it in items}
        chips = ", ".join(
            f"{pile_label(c, names.get(c, ''), private)} ({kg:,.0f} kg)"
            for c, kg in res.leftover.items()
        )
        st.caption(f"Material sin asignar (no conviene enviarlo ahora): {chips}")
