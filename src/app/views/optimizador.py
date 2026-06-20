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
    pack_lots,
)
from app.ui import brand, usd, usd2
from app.views.components import (
    components_table,
    explanation_block,
    lot_header_metrics,
    metal_table,
)
from domain.valuation import BlendComponent, value_blend
from optimize.optimizer import best_partition, optimize_partition

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
    c1, c2, c3 = st.columns([1.1, 1, 1])
    mode = c1.radio(
        "Cantidad de lotes", ["Automático", "Manual"], horizontal=True,
        help="Automático: el sistema prueba varias cantidades y elige la de mayor "
        "valor. Manual: vos fijás el número de lotes.",
    )
    if mode == "Manual":
        num_lots = c2.slider("Número de lotes", 1, 8, max(2, min_lots))
    else:
        num_lots = None
        c2.metric("Lotes", "auto", help="Lo decide el optimizador.")
    min_lot_kg = c3.number_input("Tamaño mínimo por lote (kg)", value=0.0, step=100.0)
    run = st.button("▶ Optimizar", type="primary", width="stretch")

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
            if num_lots is None:  # Automático: el sistema elige cuántos lotes.
                bp = best_partition(
                    items, prices, terms, max_num_lots=6,
                    min_lot_kg=min_lot_kg, max_lot_kg=final_lot_kg,
                )
                res, chosen, sweep = bp.result, bp.num_lots, bp.sweep
            else:
                res = optimize_partition(
                    items, prices, terms, num_lots=num_lots,
                    min_lot_kg=min_lot_kg, max_lot_kg=final_lot_kg,
                )
                chosen, sweep = len(res.lots), []
            # Alternativa ingenua: el mismo material en una sola mezcla.
            single = value_blend(
                [BlendComponent(it, it.quantity_kg) for it in items], prices, terms
            )
            expl = explain_partition([l.valuation for l in res.lots], single, terms)
        st.session_state.opt_result = res
        st.session_state.opt_expl = expl.to_dict()
        st.session_state.opt_container_kg = container_kg
        st.session_state.opt_final_lot_kg = final_lot_kg
        st.session_state.opt_chosen = chosen
        st.session_state.opt_sweep = sweep

    res = st.session_state.opt_result
    expl = st.session_state.opt_expl
    if not res.lots:
        st.warning(f"Sin solución (status={res.status}).")
        return

    container_kg = st.session_state.get("opt_container_kg", 23_000.0)
    final_lot_kg = st.session_state.get("opt_final_lot_kg", DEFAULT_FINAL_LOT_KG)
    shipped_kg = sum(l.total_weight_kg for l in res.lots)
    plan = containers_needed(shipped_kg, container_kg)

    # --- Titular: el % manda, el $ de referencia -------------------------- #
    gross = sum(l.valuation.gross_metal_total for l in res.lots)
    paid = sum(l.valuation.metal_total for l in res.lots)
    net = sum(l.valuation.net_value_usd for l in res.lots)
    util = 100.0 * paid / gross if gross else 0.0
    net_util = 100.0 * net / gross if gross else 0.0
    st.markdown(f"### {util:.0f}% del metal aprovechado")
    st.caption(
        f"De todo el oro/plata/cobre/paladio del envío, la refinería paga el "
        f"**{util:.0f}%**; tras cargos queda **{net_util:.0f}%** neto. "
        f"Referencia: valor neto {usd2(res.net_value_usd)}."
    )
    st.markdown(expl["headline"])

    sweep = st.session_state.get("opt_sweep", [])
    chosen = st.session_state.get("opt_chosen", len(res.lots))
    if sweep and len(sweep) > 1:
        detail = " · ".join(
            f"**{k}: {usd(v)}**" if k == chosen else f"{k}: {usd(v)}"
            for k, v in sweep
        )
        st.caption(
            f"🔎 El sistema eligió **{chosen} lote(s)** automáticamente. "
            f"Valor según cantidad de lotes — {detail}. Dividir en más lotes "
            "agrega menos de $50, así que no vale la pena complicar el armado."
        )
    st.write("")

    # --- Guía de armado / logística --------------------------------------- #
    st.markdown("##### Guía de armado del envío")
    k1, k2, k3, k4 = st.columns(4)
    k1.metric("Lotes finales", f"{len(res.lots)}")
    k2.metric("Peso a enviar", f"{shipped_kg/1000:,.1f} t")
    k3.metric("Contenedores", f"{plan.n_containers}")
    k4.metric("Llenado prom.", f"{plan.fill_pct_avg:.0f}%")
    st.caption(
        f"Cada **lote final** ≤ **{final_lot_kg/1000:,.1f} t** (se arma en Miami y lo "
        f"valoriza la refinería). Cada **contenedor** de **{container_kg/1000:,.1f} t** "
        "lleva 1 lote final + **anticipo**: material del próximo lote que viaja para "
        "aprovechar el espacio y espera en Miami para el siguiente armado."
    )

    # Plan de contenedores (lote final + anticipo).
    loads = pack_lots([l.total_weight_kg for l in res.lots], container_kg, final_lot_kg)
    import pandas as pd

    rows = []
    for c in loads:
        principal = "  +  ".join(
            f"Lote {n}: {kg/1000:,.1f} t" for n, kg, anti in c.segments if not anti
        )
        anticipo = "  +  ".join(
            f"Lote {n}: {kg/1000:,.1f} t" for n, kg, anti in c.segments if anti
        )
        rows.append({
            "Contenedor": f"#{c.index}",
            "Lote final": principal or "—",
            "Anticipo (espera en Miami)": anticipo or "—",
            "Carga": f"{c.total_kg/1000:,.1f} t",
            "Llenado": f"{c.fill_pct:.0f}%",
        })
    st.dataframe(pd.DataFrame(rows), width="stretch", hide_index=True)
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
            f"Lote {i} · {_ROLE_LABEL.get(role, '')} — "
            f"{v.metal_utilization_pct:.0f}% aprovechado · "
            f"{lot.total_weight_kg/1000:,.1f} t ({lot_fill:.0f}% del tope) · "
            f"Au {v.metals['AU'].grade:.0f} g/t · ref. {usd(v.net_value_usd)}",
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
