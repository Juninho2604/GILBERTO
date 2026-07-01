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

import pandas as pd

import copy

from analysis.complete_container import analyze_completion
from app.data_access import optimizable_items
from app.logistics import CONTAINERS
from app.ui import brand, pile_label, usd
from app.views.components import completion_section, metal_table, pallet_plan_section
from app.viz3d import LotViz, container_figure
from domain.models import PRECIOUS_METALS
from domain.risk import blend_threshold_risk
from domain.valuation import BlendComponent
from optimize.optimizer import best_partition, rotation_plan

_METAL_NOMBRE = {"CU": "cobre", "AU": "oro", "AG": "plata", "PT": "platino", "PD": "paladio"}
_ROLE = {0: "LOTE RICO", 1: "MIXTO", 2: "RELLENO"}


def _lot_below_threshold(valuation) -> bool:
    """True si algún metal precioso del lote cae bajo el umbral (paga $0)."""
    return any(
        valuation.metals[m].content > 0 and valuation.metals[m].rr <= 1e-9
        for m in PRECIOUS_METALS
    )


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
    run = st.button("Armar el mejor contenedor", icon=":material/play_arrow:",
                    type="primary", width="stretch")

    n_envios = max(1, ceil(stock_kg / container_kg)) if container_kg > 0 else 1
    st.caption(
        f"Stock con ley: **{stock_kg:,.0f} kg**. Se arma **1 contenedor** de "
        f"**{container_kg/1000:,.1f} t** y se **divide en los lotes** que la refinería "
        f"procesa por separado — **sin tamaño mínimo**, buscando la división que más "
        f"paga en conjunto. Con este stock harían falta ~**{n_envios} envíos** "
        f"(≈ 1 cada 3 meses)."
    )

    if run:
        with st.spinner("Armando el contenedor y dividiéndolo en lotes óptimos…"):
            bp = best_partition(
                items, prices, terms, max_num_lots=8, container_kg=container_kg,
                k_safe=float(st.session_state.get("k_safe", 1.0)),
            )
        from applog import get_logger

        get_logger("aurix.optimizador").info(
            "Contenedor optimizado: %.0f kg, %d lotes, status=%s",
            container_kg, len(bp.result.lots), bp.result.status,
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
    if res.status != "Optimal":
        st.warning(
            f"El optimizador se detuvo por límite de tiempo (status: "
            f"**{res.status}**): la división mostrada es válida pero podría no "
            f"ser la mejor posible. Volvé a correrlo o reducí las pilas.",
            icon=":material/timer:",
        )

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

    # Por qué esa división.
    if len(bp.sweep) > 1:
        probadas = ", ".join(str(k) for k, _ in bp.sweep)
        st.caption(
            f"El sistema probó dividir el contenedor en {probadas} lote(s) "
            f"(**sin tamaño mínimo**) y eligió **{bp.num_lots}**: es la división que "
            f"más paga en conjunto. Dividir aún más deja metales bajo el umbral de "
            f"la refinería y ya no suma."
        )
    st.write("")

    # --- 3D: el contenedor armado ----------------------------------------- #
    st.markdown("##### El contenedor, en 3D")
    st.caption("Cada bloque es un **lote** (tamaño = peso, color = % que paga: "
               "verde = alto, ámbar = bajo). Arrastrá para rotar, scroll para zoom.")
    viz = [
        LotViz(
            index=i + 1,
            weight_kg=l.total_weight_kg,
            util_pct=l.valuation.metal_utilization_pct,
            au_grade=l.valuation.metals["AU"].grade,
            codes=[p.item.code for p in l.components],
            below_threshold=_lot_below_threshold(l.valuation),
        )
        for i, l in enumerate(res.lots)
    ]
    st.plotly_chart(
        container_figure(viz, container_kg),
        use_container_width=True,
        config={"displayModeBar": False},
    )

    # --- Plano de carga: distribución de pallets ------------------------- #
    st.markdown("##### Plano de carga · distribución de pallets")
    st.caption(
        "Cómo iría distribuido físicamente el contenedor, pallet por pallet y en "
        "orden de carga: el sistema separa los **muy ricos** (concentran el oro) "
        "de los de **relleno**, cuidando que ni el relleno caiga bajo el umbral."
    )
    pallet_plan_section(viz, container_kg)

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
                f"Lote {i} · **{_METAL_NOMBRE[m]}**: {grade:.1f} g/t < umbral "
                f"{ded:.0f} g/t → paga $0. Sumar pilas más ricas en {_METAL_NOMBRE[m]}.",
                icon=":material/warning:",
            )
    else:
        st.success("Todos los metales superan el umbral: **no se pierde material en $0**.",
                   icon=":material/check_circle:")
    st.write("")

    # --- Riesgo de umbral a nivel contenedor ------------------------------ #
    z_min = float(st.session_state.get("z_min", 1.5))
    fragile = []
    for i, l in enumerate(res.lots, 1):
        comps = [BlendComponent(p.item, p.weight_kg) for p in l.components]
        for m, r in blend_threshold_risk(comps, terms).items():
            if r.counts_value and not r.safe(z_min):
                fragile.append((i, m, r))
    if fragile:
        for i, m, r in fragile:
            st.warning(
                f"Lote {i} · **{_METAL_NOMBRE[m]}**: la mezcla queda en "
                f"{r.grade:.0f} ±{r.sigma:.0f} g/t vs umbral {r.threshold:.0f} → "
                f"probabilidad de cobro **{r.p_cobro*100:.0f}%** (z={r.z:.1f} < "
                f"{z_min:.1f}). Riesgo de que la refinería analice por debajo y no "
                f"pague ese metal. Conviene diluir con una pila más rica.",
                icon=":material/warning:",
            )

    # --- Detalle de cada lote --------------------------------------------- #
    st.markdown("##### Lotes del contenedor")
    for i, l in enumerate(res.lots, 1):
        v = l.valuation
        comps = [BlendComponent(p.item, p.weight_kg) for p in l.components]
        risk = blend_threshold_risk(comps, terms)
        with st.expander(
            f"{_ROLE.get(i-1, 'LOTE')} {i} — {v.metal_utilization_pct:.0f}% "
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
                st.dataframe(pd.DataFrame(rows), width="stretch", hide_index=True, height=240)
            with cc2:
                st.caption("Cuánto paga cada metal (barra = % recuperado)")
                metal_table(v)

            # Riesgo de umbral por metal: ley ± σ, P_cobro, semáforo.
            st.caption("Seguridad de cobro por metal (ley ± margen vs. umbral)")
            rrows = []
            for m, r in risk.items():
                if r.grade <= 0:
                    continue
                sem = "Seguro" if r.safe(z_min) else ("Medio" if r.z >= 0 else "Riesgo")
                rrows.append({
                    "Metal": m,
                    "Ley ± σ (g/t)": f"{r.grade:.0f} ± {r.sigma:.0f}",
                    "Umbral": f"{r.threshold:.0f}",
                    "P. cobro": f"{r.p_cobro*100:.0f}%",
                    "Cobro": sem,
                })
            if rrows:
                st.dataframe(pd.DataFrame(rrows), width="stretch", hide_index=True)

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

        # --- Completar el próximo contenedor: qué comprar ----------------- #
        st.markdown("##### Completar el próximo contenedor · qué comprar")
        st.caption(
            "El sobrante suele estar dominado por pilas de bajo grado: solo, algún "
            "metal cae bajo el umbral y paga $0. El sistema detecta cuáles y "
            "recomienda qué pila comprar —y cuántos kg— para que el próximo "
            "contenedor no pierda material."
        )
        by_code = {it.code: it for it in items}
        left_items = []
        for c, kg in leftover:
            if c in by_code:
                it = copy.copy(by_code[c])
                it.quantity_kg = kg
                left_items.append(it)
        plan = analyze_completion(
            left_items, items, prices, terms,
            k_safe=float(st.session_state.get("k_safe", 1.0)),
        )
        completion_section(plan)

    # --- Plan de rotación: todos los envíos hasta agotar el stock --------- #
    st.markdown("##### Plan de rotación · todo el inventario, envío por envío")
    st.caption(
        "Simula los envíos sucesivos hasta rotar todo el stock: cuántos "
        "contenedores lleva, qué viaja en cada uno, y qué pilas **no salen "
        "nunca** — mercancía que envejece en el galpón y necesita refuerzo, "
        "ensayo de laboratorio o venta aparte."
    )
    if st.button("Calcular plan de rotación", icon=":material/route:"):
        with st.spinner("Simulando los envíos hasta agotar el stock…"):
            st.session_state["rot_plan"] = rotation_plan(
                items, prices, terms, container_kg=container_kg,
                k_safe=float(st.session_state.get("k_safe", 1.0)),
            )
    rot = st.session_state.get("rot_plan")
    if rot is not None:
        if rot.shipments:
            rrows = [
                {
                    "Envío": f"#{s.index}",
                    "Carga (t)": round(s.total_kg / 1000, 1),
                    "Aprovechado": f"{s.util_pct:.0f}%",
                    "Lotes": s.num_lots,
                    "Pilas": ", ".join(pile_label(c) for c in s.codes[:8])
                    + ("…" if len(s.codes) > 8 else ""),
                }
                for s in rot.shipments
            ]
            st.dataframe(pd.DataFrame(rrows), width="stretch", hide_index=True)
            st.caption(
                f"**{len(rot.shipments)} envío(s)** para rotar "
                f"{rot.total_shipped_kg/1000:,.1f} t (≈ "
                f"{len(rot.shipments) * 3} meses al ritmo actual)."
            )
        if rot.stuck:
            chips = " · ".join(
                f"{pile_label(c)} ({kg:,.0f} kg)"
                for c, kg in sorted(rot.stuck.items(), key=lambda x: -x[1])
            )
            st.warning(
                f"**Pilas que no salen en ningún envío** ({sum(rot.stuck.values())/1000:,.1f} t): "
                f"{chips}. El optimizador las deja porque restan valor tal como "
                f"están: conviene reforzarlas (ver *Completar*), mandarlas a "
                f"laboratorio o venderlas aparte antes de que envejezcan.",
                icon=":material/inventory:",
            )
        elif rot.shipments:
            st.success("Todo el stock rota: ninguna pila queda estancada.",
                       icon=":material/check_circle:")
