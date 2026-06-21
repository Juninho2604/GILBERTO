"""Demo — toma un lote real del histórico y lo optimiza automáticamente.

Pensada para la reunión: se elige (al azar o a mano) un lote que ya se le envió a
la refinería y el sistema muestra, **en %**, la comparación entre cómo se mandó y
cómo lo armaría óptimo, con la explicación de por qué elige esa versión.

> Foco en el **% del material que se cobra**, no en montos: el precio de los
> metales varía mucho en el mercado internacional, así que un valor en USD de hace
> un año no sirve. El % de aprovechamiento es lo estable y comparable.
"""

from __future__ import annotations

import random

import pandas as pd
import streamlit as st

from analysis.explain import explain_partition
from app.data_access import demo_lot, resolvable_lot_ids
from app.ui import brand, pile_label
from app.views.components import explanation_block, metal_table
from app.viz3d import LotViz, container_figure
from domain.risk import blend_threshold_risk
from domain.valuation import BlendComponent, value_blend
from optimize.optimizer import best_partition

_METAL_NOMBRE = {"CU": "Cobre", "AU": "Oro", "AG": "Plata", "PT": "Platino", "PD": "Paladio"}
_ROLE = {0: "LOTE RICO", 1: "MIXTO", 2: "RELLENO"}


def _recovery_pct(metals: dict, m: str) -> float:
    r = metals[m]
    return 100.0 * r.recovered / r.content if r.content > 0 else 0.0


def render() -> None:
    prices = st.session_state.prices
    terms = st.session_state.terms
    z_min = float(st.session_state.get("z_min", 1.5))

    brand(
        "Demo · un lote real, optimizado automáticamente",
        "Elegí un envío del histórico y el sistema lo reconoce y lo arma óptimo.",
    )
    st.write("")

    ids = resolvable_lot_ids()
    if not ids:
        st.warning("No hay lotes resolubles en el histórico.")
        return

    # --- Selector de lote (control único por índice, sin conflictos) ------ #
    if st.session_state.get("demo_id") not in ids:
        st.session_state["demo_id"] = ids[0]
    c1, c2 = st.columns([1, 1.4])
    if c1.button("Tomar un lote al azar", icon=":material/casino:",
                 type="primary", width="stretch"):
        st.session_state["demo_id"] = random.choice(ids)
    sel = c2.selectbox(
        "Buscar lote histórico", ids,
        index=ids.index(st.session_state["demo_id"]),
        help="Escribí para filtrar, o tocá el botón para uno al azar.",
    )
    st.session_state["demo_id"] = sel

    data = demo_lot(sel)
    if not data or not data["items"]:
        st.warning("No se pudo reconstruir ese lote.")
        return

    st.markdown(f"### Lote #{data['customer_lot']} · {data['wmt']/1000:,.1f} t")
    st.caption(
        f"Receta original (por código): **{data['recipe_raw']}**. La comparación es "
        f"en **% del metal que paga la refinería** — no en USD, porque el precio "
        f"internacional de los metales varía y un monto de hace un año no aplica."
    )
    st.write("")

    # --- Las dos versiones del mismo material ----------------------------- #
    items = data["items"]
    enviado = value_blend(
        [BlendComponent(it, it.quantity_kg) for it in items], prices, terms
    )  # "como se envió": todo en una sola mezcla
    with st.spinner("Optimizando el lote…"):
        # k_safe=0: compara el MISMO material mejor mezclado (sin descartar pilas),
        # para que la comparación sea pareja. El riesgo por metal se muestra igual.
        bp = best_partition(items, prices, terms, max_num_lots=3, k_safe=0.0)
    res = bp.result
    if not res.lots:
        st.info("Lote muy chico para repartir; ya está óptimo como una sola mezcla.")
        return

    gross = sum(l.valuation.gross_metal_total for l in res.lots)
    paid = sum(l.valuation.metal_total for l in res.lots)
    net = sum(l.valuation.net_value_usd for l in res.lots)
    util_opt = 100.0 * paid / gross if gross else 0.0
    netutil_opt = 100.0 * net / gross if gross else 0.0

    # --- 1) Comparación general (tabla, en %) ----------------------------- #
    st.markdown("##### Comparación · cómo se envió vs. cómo lo optimiza el sistema")
    comp = pd.DataFrame(
        [
            {"Métrica": "Material aprovechado",
             "Como se envió": f"{enviado.metal_utilization_pct:.0f}%",
             "Optimizado": f"{util_opt:.0f}%"},
            {"Métrica": "Neto tras cargos",
             "Como se envió": f"{enviado.net_utilization_pct:.0f}%",
             "Optimizado": f"{netutil_opt:.0f}%"},
            {"Métrica": "Lotes en que se divide",
             "Como se envió": "1", "Optimizado": f"{len(res.lots)}"},
        ]
    )
    st.dataframe(comp, width="stretch", hide_index=True)

    gain = util_opt - enviado.metal_utilization_pct
    if gain >= 0.5:
        st.success(
            f"Optimizando, la refinería paga **{gain:.0f} puntos más** del material "
            f"({enviado.metal_utilization_pct:.0f}% → {util_opt:.0f}%).",
            icon=":material/trending_up:",
        )
    else:
        st.info(
            "En este lote la mezcla original ya era muy buena: el sistema la "
            "confirma y la separa en lotes seguros sin perder aprovechamiento.",
            icon=":material/verified:",
        )

    # --- 2) Comparación por metal (% recuperado) -------------------------- #
    st.markdown("##### Cuánto paga cada metal (% recuperado)")
    opt_metals_recovered = {}
    opt_metals_content = {}
    for l in res.lots:
        for m, r in l.valuation.metals.items():
            opt_metals_recovered[m] = opt_metals_recovered.get(m, 0.0) + r.recovered
            opt_metals_content[m] = opt_metals_content.get(m, 0.0) + r.content
    rows = []
    for m in ("AU", "AG", "CU", "PD"):
        if enviado.metals[m].content <= 0:
            continue
        env = _recovery_pct(enviado.metals, m)
        opt = (100.0 * opt_metals_recovered.get(m, 0.0) / opt_metals_content[m]
               if opt_metals_content.get(m, 0) > 0 else 0.0)
        rows.append({
            "Metal": _METAL_NOMBRE[m],
            "Como se envió": f"{env:.0f}%",
            "Optimizado": f"{opt:.0f}%",
            "Diferencia": f"{opt - env:+.0f} pts" if abs(opt - env) >= 0.5 else "=",
        })
    if rows:
        st.dataframe(pd.DataFrame(rows), width="stretch", hide_index=True)

    # --- 3) Por qué el sistema elige esta versión ------------------------- #
    st.markdown("##### ¿Por qué el sistema elige esta versión?")
    expl = explain_partition([l.valuation for l in res.lots], enviado, terms)
    explanation_block(expl.to_dict())
    st.write("")

    # --- 4) El contenedor en 3D ------------------------------------------- #
    st.markdown("##### El lote óptimo, en 3D")
    shipped = sum(l.total_weight_kg for l in res.lots)
    viz = [
        LotViz(index=i + 1, weight_kg=l.total_weight_kg,
               util_pct=l.valuation.metal_utilization_pct,
               au_grade=l.valuation.metals["AU"].grade,
               codes=[p.item.code for p in l.components])
        for i, l in enumerate(res.lots)
    ]
    st.caption("Cada bloque es un lote (tamaño = peso, color = % que paga: verde "
               "= alto, ámbar = bajo). Arrastrá para rotar.")
    st.plotly_chart(
        container_figure(viz, max(shipped, 1.0)),
        use_container_width=True, config={"displayModeBar": False},
    )

    # --- 5) Seguridad de cobro y confianza por lote ----------------------- #
    st.markdown("##### Seguridad y confianza por lote")
    for i, l in enumerate(res.lots, 1):
        v = l.valuation
        comps = [BlendComponent(p.item, p.weight_kg) for p in l.components]
        risk = blend_threshold_risk(comps, terms)
        with st.expander(
            f"{_ROLE.get(i-1, 'LOTE')} {i} — {v.metal_utilization_pct:.0f}% "
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
                sem = "Seguro" if r.safe(z_min) else ("Medio" if r.z >= 0 else "Riesgo")
                rrows.append({
                    "Metal": _METAL_NOMBRE.get(m, m), "Ley ± σ": f"{r.grade:.0f} ± {r.sigma:.0f}",
                    "Umbral": f"{r.threshold:.0f}", "P. cobro": f"{r.p_cobro*100:.0f}%",
                    "Cobro": sem,
                })
            if rrows:
                st.caption("Seguridad de cobro por metal (probabilidad de superar el umbral)")
                st.dataframe(pd.DataFrame(rrows), width="stretch", hide_index=True)
