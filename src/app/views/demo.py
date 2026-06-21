"""Demo — toma un lote real del histórico y lo optimiza automáticamente.

Pensada para la reunión con Gilberto: se elige (al azar o a mano) un lote que él
ya le envió a la refinería, el sistema lo **reconoce y reproduce lo que se pagó**
(prueba de confianza) y muestra cómo lo **armaría óptimo** con todo el motor: %
aprovechado, contenedor en 3D, riesgo de cobro por metal y confianza de las leyes.
"""

from __future__ import annotations

import random

import pandas as pd
import streamlit as st

from app.data_access import demo_lot, resolvable_lot_ids
from app.ui import brand, pile_label, usd
from app.views.components import metal_table
from app.viz3d import LotViz, container_figure
from domain.risk import blend_threshold_risk
from domain.valuation import BlendComponent, value_lot
from optimize.optimizer import best_partition

_METAL_NOMBRE = {"CU": "cobre", "AU": "oro", "AG": "plata", "PT": "platino", "PD": "paladio"}
_ROLE = {0: "🥇 LOTE RICO", 1: "⚖️ MIXTO", 2: "🧱 RELLENO"}


def render() -> None:
    prices = st.session_state.prices
    terms = st.session_state.terms
    z_min = float(st.session_state.get("z_min", 1.5))
    k_safe = float(st.session_state.get("k_safe", 1.0))

    brand(
        "Demo · un lote real, optimizado automáticamente",
        "Tomamos un envío del histórico de la refinería y el sistema lo reconoce, "
        "reproduce el pago y arma la mezcla óptima.",
    )
    st.write("")

    ids = resolvable_lot_ids()
    if not ids:
        st.warning("No hay lotes resolubles en el histórico.")
        return

    c1, c2 = st.columns([1, 1.4])
    if c1.button("🎲 Tomar un lote al azar", type="primary", width="stretch"):
        st.session_state.demo_id = random.choice(ids)
    if "demo_id" not in st.session_state:
        st.session_state.demo_id = random.choice(ids)
    picked = c2.selectbox(
        "…o elegí uno", ids, index=ids.index(st.session_state.demo_id),
        key="demo_pick",
    )
    if picked != st.session_state.demo_id:
        st.session_state.demo_id = picked

    data = demo_lot(st.session_state.demo_id)
    if not data or not data["items"]:
        st.warning("No se pudo reconstruir ese lote.")
        return

    # --- 1) Lo que se envió y lo que pagó la refinería -------------------- #
    measured = value_lot(data["wmt"], data["moisture"], data["measured_grades"], prices, terms)
    st.markdown(f"### Lote #{data['customer_lot']} · {data['wmt']/1000:,.1f} t")
    st.caption(
        f"Receta original (por código): **{data['recipe_raw']}**. El sistema lo "
        f"valoriza con las leyes **medidas** por la refinería ese envío."
    )
    a, b, c = st.columns(3)
    a.metric("Material aprovechado", f"{measured.metal_utilization_pct:.0f}%",
             help="Del metal del lote, qué % superó los mínimos y se cobró.")
    b.metric("No aprovechado", f"{measured.unused_pct:.0f}%", delta="bajo el umbral",
             delta_color="off")
    c.metric("Valor (ref.)", usd(measured.net_value_usd),
             help="Lo que paga la fórmula de la refinería a precios de referencia.")
    st.write("")

    # --- 2) Cómo lo arma el sistema (optimizado) -------------------------- #
    st.markdown("##### Así lo arma el sistema")
    with st.spinner("Optimizando el lote…"):
        bp = best_partition(
            data["items"], prices, terms, max_num_lots=3, k_safe=k_safe,
        )
    res = bp.result
    if not res.lots:
        st.info("Este lote es muy chico para repartir; ya está óptimo como una sola mezcla.")
        return

    gross = sum(l.valuation.gross_metal_total for l in res.lots)
    paid = sum(l.valuation.metal_total for l in res.lots)
    util_opt = 100.0 * paid / gross if gross else 0.0
    shipped = sum(l.total_weight_kg for l in res.lots)

    k1, k2, k3 = st.columns(3)
    k1.metric("Material aprovechado", f"{util_opt:.0f}%",
              delta=f"{util_opt - measured.metal_utilization_pct:+.0f} pts vs. medido",
              delta_color="normal")
    k2.metric("Lotes en que lo divide", f"{len(res.lots)}")
    k3.metric("Material colocado", f"{shipped/1000:,.1f} t")

    viz = [
        LotViz(index=i + 1, weight_kg=l.total_weight_kg,
               util_pct=l.valuation.metal_utilization_pct,
               au_grade=l.valuation.metals["AU"].grade,
               codes=[p.item.code for p in l.components])
        for i, l in enumerate(res.lots)
    ]
    st.caption("Cada bloque es un lote (tamaño = peso, color = % que paga). "
               "Arrastrá para rotar.")
    st.plotly_chart(
        container_figure(viz, max(shipped, 1.0)),
        use_container_width=True, config={"displayModeBar": False},
    )

    # --- 3) Riesgo de cobro y confianza (lo que vuelve creíble al modelo) -- #
    st.markdown("##### Seguridad y confianza")
    for i, l in enumerate(res.lots, 1):
        v = l.valuation
        comps = [BlendComponent(p.item, p.weight_kg) for p in l.components]
        risk = blend_threshold_risk(comps, terms)
        with st.expander(
            f"{_ROLE.get(i-1, '📦 LOTE')} {i} — {v.metal_utilization_pct:.0f}% "
            f"aprovechado · {l.total_weight_kg/1000:,.1f} t",
            expanded=(i == 1),
        ):
            cc1, cc2 = st.columns([1, 1])
            with cc1:
                st.caption("Pilas (por código)")
                st.dataframe(
                    pd.DataFrame([
                        {"Pila": pile_label(p.item.code), "kg": round(p.weight_kg, 0)}
                        for p in sorted(l.components, key=lambda p: -p.weight_kg)
                    ]), width="stretch", hide_index=True, height=200,
                )
            with cc2:
                st.caption("Pago por metal")
                metal_table(v)
            rrows = []
            for m, r in risk.items():
                if r.grade <= 0:
                    continue
                sem = "🟢" if r.safe(z_min) else ("🟡" if r.z >= 0 else "🔴")
                rrows.append({
                    "Metal": m, "Ley ± σ": f"{r.grade:.0f} ± {r.sigma:.0f}",
                    "Umbral": f"{r.threshold:.0f}", "P. cobro": f"{r.p_cobro*100:.0f}%",
                    "Seguro": sem,
                })
            if rrows:
                st.caption("Seguridad de cobro por metal (probabilidad de superar el umbral)")
                st.dataframe(pd.DataFrame(rrows), width="stretch", hide_index=True)

    st.write("")
    st.success(
        f"✅ El sistema **reconoció** un lote real, reprodujo su valorización, lo "
        f"**repartió en {len(res.lots)} lote(s) óptimos**, mostró el contenedor en "
        f"3D y evaluó el **riesgo de cobro** y la **confianza** de cada ley — todo "
        f"automático, sobre los datos reales de la refinería."
    )
