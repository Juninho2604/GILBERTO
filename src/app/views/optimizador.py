"""Optimizador — arma EL MEJOR CONTENEDOR para enviar, como varios lotes.

Gilberto manda ~1 contenedor (23 t, 40') cada 3 meses. La refinería **tasa lotes
por separado** dentro del contenedor. Por eso el sistema arma el próximo
contenedor y lo **parte en los lotes óptimos**: concentra el oro para tocar el
tope (96%) y separa el relleno, buscando el mayor % del material pagado sin dejar
nada en $0. El resto del stock espera el siguiente envío.
"""

from __future__ import annotations

from math import ceil

import streamlit as st

from app.data_access import optimizable_items
from app.logistics import CONTAINERS
from app.ui import brand, pile_label, usd
from app.views.components import metal_table
from app.viz3d import LotViz, container_figure
from domain.models import PRECIOUS_METALS
from optimize.optimizer import best_partition

_METAL_NOMBRE = {"CU": "cobre", "AU": "oro", "AG": "plata", "PT": "platino", "PD": "paladio"}
_ROLE = {0: "🥇 LOTE RICO", 1: "⚖️ MIXTO", 2: "🧱 RELLENO"}


def render() -> None:
    prices = st.session_state.prices
    terms = st.session_state.terms

    brand(
        "Optimizador — el mejor contenedor para enviar",
        "Arma el contenedor de 23 t y lo divide en sus lotes óptimos: el mayor % "
        "del material pagado, sin dejar nada en $0.",
    )
    st.write("")

    items = optimizable_items()
    stock_kg = sum(it.quantity_kg for it in items)

    # --- Contenedor a enviar ---------------------------------------------- #
    st.markdown("##### Contenedor a enviar")
    g1, g2 = st.columns([1.3, 1])
    cont_name = g1.selectbox("Tipo de contenedor", list(CONTAINERS), index=0)
    cont_default = CONTAINERS[cont_name] or 23_000.0
    container_kg = g2.number_input(
        "Capacidad (kg)", value=float(cont_default), step=500.0,
        help="Carga máxima del contenedor (estándar 40' ≈ 23 t).",
    )
    run = st.button("▶ Armar el mejor contenedor", type="primary", width="stretch")

    n_envios = max(1, ceil(stock_kg / container_kg)) if container_kg > 0 else 1
    st.caption(
        f"Stock con ley: **{stock_kg:,.0f} kg**. Se arma **1 contenedor** de "
        f"**{container_kg/1000:,.1f} t** dividido en los lotes que la refinería tasa "
        f"por separado. Con este stock harían falta ~**{n_envios} envíos** "
        f"(≈ 1 cada 3 meses)."
    )

    if run:
        with st.spinner("Armando el contenedor y dividiéndolo en lotes óptimos…"):
            bp = best_partition(
                items, prices, terms, max_num_lots=5, container_kg=container_kg,
            )
        st.session_state.cont_bp = bp
        st.session_state.cont_kg = container_kg

    if "cont_bp" not in st.session_state:
        st.info("Elegí el contenedor y tocá **Armar el mejor contenedor**.")
        return

    bp = st.session_state.cont_bp
    container_kg = st.session_state.get("cont_kg", container_kg)
    res = bp.result
    if not res.lots:
        st.warning(f"Sin solución (status={res.status}).")
        return

    # --- Aprovechamiento del contenedor (el % manda) ---------------------- #
    gross = sum(l.valuation.gross_metal_total for l in res.lots)
    paid = sum(l.valuation.metal_total for l in res.lots)
    net = sum(l.valuation.net_value_usd for l in res.lots)
    shipped = sum(l.total_weight_kg for l in res.lots)
    util = 100.0 * paid / gross if gross else 0.0
    net_util = 100.0 * net / gross if gross else 0.0
    fill = 100.0 * shipped / container_kg if container_kg else 0.0

    st.markdown(f"### {util:.0f}% del material aprovechado")
    st.caption(
        f"El contenedor va en **{len(res.lots)} lote(s)**. De todo su metal, la "
        f"refinería paga el **{util:.0f}%**; tras cargos queda **{net_util:.0f}%** "
        f"neto. Referencia: {usd(net)}."
    )

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Material aprovechado", f"{util:.0f}%")
    m2.metric("No aprovechado", f"{100-util:.0f}%", delta="bajo el mínimo", delta_color="off")
    m3.metric("Lotes en el contenedor", f"{len(res.lots)}")
    m4.metric("Carga", f"{shipped/1000:,.1f} t", delta=f"{fill:.0f}% lleno", delta_color="off")
    st.write("")

    # --- 3D: el contenedor armado ----------------------------------------- #
    st.markdown("##### El contenedor, en 3D")
    st.caption("Cada bloque es un **lote** (tamaño = peso, color = % que paga: "
               "🟢 alto · 🟠 bajo). Arrastrá para rotar, scroll para zoom.")
    viz = [
        LotViz(
            index=i + 1,
            weight_kg=l.total_weight_kg,
            util_pct=l.valuation.metal_utilization_pct,
            au_grade=l.valuation.metals["AU"].grade,
            codes=[p.item.code for p in l.components],
        )
        for i, l in enumerate(res.lots)
    ]
    st.plotly_chart(
        container_figure(viz, container_kg),
        use_container_width=True,
        config={"displayModeBar": False},
    )

    # --- ¿Algo queda en $0? (a nivel contenedor) -------------------------- #
    wasted = []
    for i, l in enumerate(res.lots, 1):
        for m in PRECIOUS_METALS:
            r = l.valuation.metals[m]
            if r.content > 0 and r.rr <= 1e-9:
                wasted.append((i, m, r.grade, terms.rule(m).deduction))
    if wasted:
        for i, m, grade, ded in wasted:
            st.warning(
                f"⚠️ Lote {i} · **{_METAL_NOMBRE[m]}**: {grade:.1f} g/t < umbral "
                f"{ded:.0f} g/t → paga $0. Sumar pilas más ricas en {_METAL_NOMBRE[m]}."
            )
    else:
        st.success("✅ Todos los metales superan el umbral: **no se pierde material en $0**.")
    st.write("")

    # --- Detalle de cada lote --------------------------------------------- #
    st.markdown("##### Lotes del contenedor")
    for i, l in enumerate(res.lots, 1):
        v = l.valuation
        with st.expander(
            f"{_ROLE.get(i-1, '📦 LOTE')} {i} — {v.metal_utilization_pct:.0f}% "
            f"aprovechado · {l.total_weight_kg/1000:,.1f} t · Au {v.metals['AU'].grade:.0f} g/t",
            expanded=(i == 1),
        ):
            cc1, cc2 = st.columns([1, 1])
            with cc1:
                st.caption("Pilas del lote (por código)")
                rows = [
                    {
                        "Pila": pile_label(p.item.code),
                        "kg": round(p.weight_kg, 0),
                        "%": round(100.0 * p.weight_kg / l.total_weight_kg, 1),
                    }
                    for p in sorted(l.components, key=lambda p: -p.weight_kg)
                ]
                import pandas as pd
                st.dataframe(pd.DataFrame(rows), width="stretch", hide_index=True, height=240)
            with cc2:
                st.caption("Cuánto paga cada metal (barra = % recuperado)")
                metal_table(v)

    # --- Qué queda para el próximo contenedor ----------------------------- #
    assigned: dict[str, float] = {}
    for l in res.lots:
        for p in l.components:
            assigned[p.item.code] = assigned.get(p.item.code, 0.0) + p.weight_kg
    leftover = [
        (it.code, it.quantity_kg - assigned.get(it.code, 0.0))
        for it in items
        if it.quantity_kg - assigned.get(it.code, 0.0) > 1.0
    ]
    if leftover:
        left_kg = sum(kg for _, kg in leftover)
        st.markdown("##### Queda en depósito para el próximo contenedor")
        chips = " · ".join(
            f"{pile_label(c)} ({kg:,.0f} kg)"
            for c, kg in sorted(leftover, key=lambda x: -x[1])
        )
        st.caption(f"**{left_kg/1000:,.1f} t** en {len(leftover)} pilas: {chips}")
