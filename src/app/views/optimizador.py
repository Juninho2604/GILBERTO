"""Optimizador — arma EL MEJOR CONTENEDOR para enviar (1 envío por vez).

Gilberto manda en promedio **1 contenedor (~23 t) cada 3 meses**. Por eso el
sistema no reparte todo el inventario de una: optimiza **el próximo contenedor**,
buscando la mezcla que pague el **mayor % del material** sin dejar nada en $0 por
no llegar al umbral. El resto del stock espera el siguiente envío.
"""

from __future__ import annotations

from math import ceil

import streamlit as st

from app.data_access import optimizable_items
from app.logistics import CONTAINERS
from app.ui import usd, brand, pile_label
from app.views.components import components_table, metal_table
from domain.models import PRECIOUS_METALS
from optimize.optimizer import optimize_blend

_METAL_NOMBRE = {"CU": "cobre", "AU": "oro", "AG": "plata", "PT": "platino", "PD": "paladio"}


def render() -> None:
    prices = st.session_state.prices
    terms = st.session_state.terms

    brand(
        "Optimizador — el mejor contenedor para enviar",
        "Arma el contenedor que paga el mayor % del material, sin dejar nada en $0.",
    )
    st.write("")

    items = optimizable_items()  # solo pilas con ley (sin peso muerto sin ensayo)
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

    target = min(container_kg, stock_kg)
    n_envios = max(1, ceil(stock_kg / container_kg)) if container_kg > 0 else 1
    st.caption(
        f"Stock con ley: **{stock_kg:,.0f} kg**. Se arma **1 contenedor** de "
        f"**{container_kg/1000:,.1f} t** (el próximo envío). Con este stock harían "
        f"falta ~**{n_envios} envíos** (≈ 1 cada 3 meses). El resto espera su turno."
    )

    if run:
        with st.spinner("Buscando la mejor mezcla para el contenedor…"):
            res = optimize_blend(
                items, prices, terms,
                objective="net_usd", min_lot_kg=target, max_lot_kg=container_kg,
            )
        st.session_state.cont_result = res
        st.session_state.cont_container_kg = container_kg

    if "cont_result" not in st.session_state:
        st.info("Elegí el contenedor y tocá **Armar el mejor contenedor**.")
        return

    res = st.session_state.cont_result
    container_kg = st.session_state.get("cont_container_kg", container_kg)
    if not res.components or res.valuation is None:
        st.warning(f"Sin solución (status={res.status}).")
        return
    v = res.valuation

    # --- Titular: el % manda ---------------------------------------------- #
    st.markdown(f"### {v.metal_utilization_pct:.0f}% del material aprovechado")
    st.caption(
        f"De todo el metal del contenedor, la refinería paga el "
        f"**{v.metal_utilization_pct:.0f}%**; tras cargos queda "
        f"**{v.net_utilization_pct:.0f}%** neto. Referencia: {usd(v.net_value_usd)}."
    )
    st.write("")

    fill_pct = 100.0 * res.total_weight_kg / container_kg if container_kg else 0.0
    m1, m2, m3 = st.columns(3)
    m1.metric("Material aprovechado", f"{v.metal_utilization_pct:.0f}%")
    m2.metric("No aprovechado", f"{v.unused_pct:.0f}%",
              delta="se pierde bajo el mínimo", delta_color="off")
    m3.metric("Contenedor", f"{res.total_weight_kg/1000:,.1f} t",
              delta=f"{fill_pct:.0f}% lleno", delta_color="off")

    # --- ¿Algo queda en $0? ----------------------------------------------- #
    wasted = []
    for m in PRECIOUS_METALS:
        r = v.metals[m]
        if r.content > 0 and r.rr <= 1e-9:
            rule = terms.rule(m)
            wasted.append((m, r.grade, rule.deduction, r.content))
    if wasted:
        for m, grade, ded, content in wasted:
            st.warning(
                f"⚠️ **{_METAL_NOMBRE[m].capitalize()}**: la mezcla queda en "
                f"{grade:.1f} g/t, por debajo del umbral de {ded:.0f} g/t → paga "
                f"**$0** ({content:,.0f} g presentes). Para cobrarlo haría falta "
                f"sumar pilas más ricas en {_METAL_NOMBRE[m]}."
            )
    else:
        st.success(
            "✅ Todos los metales con contenido superan el umbral de la refinería: "
            "**no se pierde material en $0** en este contenedor."
        )
    st.write("")

    # --- La mezcla (solo códigos) ----------------------------------------- #
    st.markdown("##### Qué cargar en el contenedor")
    st.caption("Cada pila por su **código** · cuánto entra · ley estimada.")
    comp_rows = [
        {
            "code": p.item.code,
            "name": p.item.name,
            "kg": round(p.weight_kg, 1),
            "% cont.": round(100.0 * p.weight_kg / res.total_weight_kg, 1),
            "grade_au": round(p.item.grade_au, 1),
            "grade_ag": round(p.item.grade_ag, 0),
            "grade_cu": round(p.item.grade_cu, 4),
            "grade_pd": round(p.item.grade_pd, 1),
        }
        for p in sorted(res.components, key=lambda p: -p.weight_kg)
    ]
    components_table(comp_rows, private=False)
    st.write("")

    st.markdown("##### Cuánto paga cada metal")
    st.caption("La barra de **recuperación** muestra qué % del metal se cobra (el "
               "oro topa en 96%, la plata en 95%).")
    metal_table(v)
    st.write("")

    # --- Qué queda para el próximo contenedor ----------------------------- #
    assigned = {p.item.code: p.weight_kg for p in res.components}
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
        st.caption(
            f"**{left_kg/1000:,.1f} t** en {len(leftover)} pilas esperan el "
            f"siguiente envío (≈ 3 meses): {chips}"
        )
