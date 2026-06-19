"""Optimizador — el sistema arma las mezclas óptimas y explica por qué (Fase 2)."""

from __future__ import annotations

from math import ceil

import streamlit as st

from analysis.explain import explain_partition
from app.data_access import optimizable_items
from app.logistics import (
    CONTAINERS,
    DEFAULT_FINAL_LOT_KG,
    containers_needed,
)
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

    items = optimizable_items()  # solo pilas con ley (sin peso muerto sin ensayo)
    stock_kg = sum(it.quantity_kg for it in items)

    # --- Logística de envío (contenedor + lote final) --------------------- #
    st.markdown("##### Logística de envío")
    g1, g2, g3 = st.columns([1.2, 1, 1])
    cont_name = g1.selectbox("Contenedor", list(CONTAINERS), index=0)
    cont_default = CONTAINERS[cont_name] or 23_000.0
    container_kg = g2.number_input(
        "Capacidad contenedor (kg)", value=float(cont_default), step=500.0,
        help="Capacidad de carga del contenedor (transporte hasta Miami).",
    )
    final_lot_kg = g3.number_input(
        "Tope del lote final (kg)", value=DEFAULT_FINAL_LOT_KG, step=500.0,
        help="Peso máximo del lote que se arma en Miami y valoriza la refinería "
        "(~18-19 t). El optimizador no arma lotes por encima de este tope.",
    )

    # --- Parámetros de optimización --------------------------------------- #
    min_lots = max(1, ceil(stock_kg / final_lot_kg)) if final_lot_kg > 0 else 1
    c1, c2, c3 = st.columns([1, 1, 1])
    num_lots = c1.slider("Cantidad de lotes", 1, 8, max(2, min_lots))
    min_lot_kg = c2.number_input("Tamaño mínimo por lote (kg)", value=0.0, step=100.0)
    run = c3.button("▶ Optimizar", type="primary", width="stretch")

    st.caption(
        f"Stock con ley: **{stock_kg:,.0f} kg**. Con tope de lote "
        f"{final_lot_kg:,.0f} kg hacen falta al menos **{min_lots} lote(s)** para "
        f"enviar todo. Clave del modelo: **no diluir** las pilas ricas en oro con "
        f"relleno pobre (la deducción de 7 g/t de Au pega sobre toda la masa)."
    )

    if not run and "opt_result" not in st.session_state:
        st.info("Ajustá los parámetros y tocá **Optimizar**.")
        return

    if run:
        with st.spinner("Resolviendo el modelo (MILP)…"):
            res = optimize_partition(
                items, prices, terms, num_lots=num_lots,
                min_lot_kg=min_lot_kg, max_lot_kg=final_lot_kg,
            )
            # Alternativa ingenua: el mismo material en una sola mezcla.
            single = value_blend(
                [BlendComponent(it, it.quantity_kg) for it in items], prices, terms
            )
            expl = explain_partition([l.valuation for l in res.lots], single, terms)
        st.session_state.opt_result = res
        st.session_state.opt_expl = expl.to_dict()
        st.session_state.opt_container_kg = container_kg
        st.session_state.opt_final_lot_kg = final_lot_kg

    res = st.session_state.opt_result
    expl = st.session_state.opt_expl
    if not res.lots:
        st.warning(f"Sin solución (status={res.status}).")
        return

    container_kg = st.session_state.get("opt_container_kg", 23_000.0)
    final_lot_kg = st.session_state.get("opt_final_lot_kg", DEFAULT_FINAL_LOT_KG)
    shipped_kg = sum(l.total_weight_kg for l in res.lots)
    plan = containers_needed(shipped_kg, container_kg)

    # --- Titular ---------------------------------------------------------- #
    st.markdown(f"### {usd2(res.net_value_usd)}")
    st.markdown(expl["headline"])
    st.write("")

    # --- Guía de armado / logística --------------------------------------- #
    st.markdown("##### Guía de armado del envío")
    k1, k2, k3, k4 = st.columns(4)
    k1.metric("Lotes finales", f"{len(res.lots)}")
    k2.metric("Peso a enviar", f"{shipped_kg/1000:,.1f} t")
    k3.metric("Contenedores", f"{plan.n_containers}")
    k4.metric("Llenado prom.", f"{plan.fill_pct_avg:.0f}%")
    st.caption(
        f"Cada lote ≤ tope de **{final_lot_kg/1000:,.1f} t** (lote final de Miami). "
        f"Contenedor de **{container_kg/1000:,.1f} t**: se necesitan "
        f"**{plan.n_containers}** (último al {plan.fill_pct_last:.0f}%). "
        "Cada lote entra completo en un contenedor."
    )
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
        lot_fill = 100.0 * lot.total_weight_kg / final_lot_kg if final_lot_kg else 0.0
        with st.expander(
            f"Lote {i} · {_ROLE_LABEL.get(role, '')} — {usd(v.net_value_usd)} · "
            f"{v.result_per_kg:.1f} USD/kg · {lot.total_weight_kg/1000:,.1f} t "
            f"({lot_fill:.0f}% del tope) · Au {v.metals['AU'].grade:.0f} g/t",
            expanded=(i == 1),
        ):
            cap_fill = 100.0 * lot.total_weight_kg / container_kg if container_kg else 0.0
            st.caption(
                f"📦 Armado: **{lot.total_weight_kg:,.0f} kg** "
                f"({lot.total_weight_kg/1000:,.1f} t) · {lot_fill:.0f}% del lote final · "
                f"ocupa {cap_fill:.0f}% de un contenedor de {container_kg/1000:,.0f} t."
            )
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
