"""Componentes compartidos por las vistas (tablas de lote, explicaciones)."""

from __future__ import annotations

import pandas as pd
import streamlit as st

from app.ui import pile_label, pill, usd, usd2, why
from app.viz3d import (
    RICH_FILL,
    RICH_LOW,
    RICH_VERY,
    LotViz,
    build_pallets,
    pallet_figure,
)
from domain.models import METALS
from domain.valuation import LotValuation

_ROLE_LABEL = {"rico": "LOTE RICO", "relleno": "RELLENO", "mixto": "MIXTO"}
_METAL_NOMBRE = {"CU": "Cobre", "AU": "Oro", "AG": "Plata", "PT": "Platino", "PD": "Paladio"}
_TIER_NOMBRE = {"MEASURED": "medida", "ESTIMATED": "estimada", "NOT_DETERMINED": "sin determinar"}

# Distintivo de color por categoría, alineado con el 3D.
_TIER_DOT = {
    RICH_VERY: "#228A23",
    RICH_LOW: "#78C850",
    RICH_FILL: "#D6B25A",
}


def metal_table(v: LotValuation) -> None:
    """Desglose por metal con barra de recuperación (RR)."""
    rows = []
    for m in METALS:
        r = v.metals[m]
        unit = "frac" if m == "CU" else "g/t"
        cu = "kg" if m == "CU" else "g"
        rows.append(
            {
                "Metal": m,
                f"Ley ({unit})": round(r.grade, 4 if m == "CU" else 1),
                f"Contenido ({cu})": round(r.content, 2),
                "RR": r.rr,
                "Monto USD": round(r.amount_usd, 2),
            }
        )
    df = pd.DataFrame(rows)
    st.dataframe(
        df,
        width="stretch",
        hide_index=True,
        column_config={
            "RR": st.column_config.ProgressColumn(
                "Recuperación (RR)", min_value=0.0, max_value=1.0, format="%.0f%%"
            ),
            "Monto USD": st.column_config.NumberColumn("Monto USD", format="$%.0f"),
        },
    )


def charges_breakdown(v: LotValuation) -> None:
    df = pd.DataFrame(
        [
            {"Concepto": "Metal total", "USD": round(v.metal_total, 2)},
            {"Concepto": "− Tratamiento", "USD": -round(v.treatment_charge, 2)},
            {"Concepto": "− Trituración", "USD": -round(v.shredding_charge, 2)},
            {"Concepto": "= Valor neto", "USD": round(v.net_value_usd, 2)},
        ]
    )
    st.dataframe(
        df, width="stretch", hide_index=True,
        column_config={"USD": st.column_config.NumberColumn("USD", format="$%.0f")},
    )


def lot_header_metrics(v: LotValuation) -> None:
    """Encabezado del lote: el % manda, el $ queda como referencia."""
    c1, c2, c3 = st.columns(3)
    c1.metric(
        "Material aprovechado", f"{v.metal_utilization_pct:.0f}%",
        help="Del metal presente en la mezcla, qué % paga la refinería (supera "
        "sus mínimos de deducción). El resto se pierde bajo el umbral.",
    )
    c2.metric(
        "No aprovechado", f"{v.unused_pct:.0f}%",
        delta="se pierde bajo el mínimo", delta_color="off",
        help="Metal que cae por debajo del mínimo de la refinería y paga $0.",
    )
    c3.metric(
        "Neto tras cargos", f"{v.net_utilization_pct:.0f}%",
        help="% neto sobre el metal presente, ya descontados tratamiento y "
        "trituración.",
    )
    st.caption(
        f"Referencia · {v.wmt/1000:,.1f} t · Au mezcla "
        f"{v.metals['AU'].grade:,.0f} g/t · valor neto {usd2(v.net_value_usd)} "
        f"({v.result_per_kg:,.1f} USD/kg)."
    )


def explanation_block(expl: dict) -> None:
    """Renderiza la explicación de una optimización (por qué es la mejor)."""
    if not expl:
        return
    for b in expl.get("bullets", []):
        why(b, "good")
    for lot in expl.get("lots", []):
        role = lot.get("role", "mixto")
        st.markdown(
            f"{pill(_ROLE_LABEL.get(role, role.upper()), role)} "
            f"&nbsp; **{usd(lot['net_usd'])}** · {lot['per_kg']:.1f} USD/kg · "
            f"{lot['wmt']:,.0f} kg",
            unsafe_allow_html=True,
        )
        for d in lot.get("drivers", []):
            if d["status"] in ("capped", "below_threshold") or d["amount_usd"] > 1:
                kind = {"capped": "good", "below_threshold": "warn"}.get(d["status"], "")
                st.caption("• " + d["headline"])
        for n in lot.get("notes", []):
            st.caption("· " + n)


def pallet_plan_section(lots_viz: list[LotViz], container_kg: float) -> None:
    """Plan de armado del contenedor por pallets: 3D numerado + tabla + leyenda.

    Toma los lotes ya valorizados (``LotViz``) y los parte en pallets de ~1 t,
    los clasifica en MUY RICO / POCO RICO / RELLENO y los muestra en orden de
    carga. El relleno también debe superar el umbral: si no, se marca en rojo.
    """
    if not lots_viz:
        return
    pallets = build_pallets(lots_viz)

    # Resumen por categoría.
    counts = {RICH_VERY: 0, RICH_LOW: 0, RICH_FILL: 0}
    for p in pallets:
        counts[p.tier] = counts.get(p.tier, 0) + 1
    n_below = sum(1 for p in pallets if p.below_threshold)

    st.caption(
        f"El contenedor se arma con **{len(pallets)} pallets** de ~1 t, numerados "
        f"en orden de carga. Cada pallet hereda la categoría de su lote según la "
        f"concentración de oro: **MUY RICO** concentra el valor, **POCO RICO** "
        f"aporta volumen con ley media y **RELLENO** es peso que viaja mezclado "
        f"para **no caer bajo el umbral**."
    )

    # Leyenda de colores (alineada con el 3D).
    leg = " &nbsp;&nbsp; ".join(
        f"<span style='display:inline-block;width:11px;height:11px;border-radius:2px;"
        f"background:{_TIER_DOT[t]};vertical-align:middle;margin-right:5px'></span>"
        f"<span style='vertical-align:middle'>{t} · {counts.get(t, 0)} pallet(s)</span>"
        for t in (RICH_VERY, RICH_LOW, RICH_FILL)
    )
    st.markdown(leg, unsafe_allow_html=True)

    st.plotly_chart(
        pallet_figure(pallets, container_kg),
        use_container_width=True, config={"displayModeBar": False},
    )

    if n_below:
        st.warning(
            f"**{n_below} pallet(s)** quedan con algún metal bajo el umbral "
            f"(borde rojo en el 3D): ese metal pagaría $0. Conviene mezclarlos con "
            f"pilas más ricas antes de cargar.",
            icon=":material/warning:",
        )
    else:
        st.success(
            "Todos los pallets —incluido el relleno— superan el umbral de la "
            "refinería: no hay pallets que paguen $0.",
            icon=":material/check_circle:",
        )

    # Tabla del plan de carga, pallet por pallet.
    rows = [
        {
            "Pallet": p.number,
            "Lote": p.lot_index,
            "Categoría": p.tier,
            "Peso (kg)": round(p.weight_kg, 0),
            "Au (g/t)": round(p.au_grade, 0),
            "Aprovechado": f"{p.util_pct:.0f}%",
            "Pilas": ", ".join(pile_label(c) for c in p.codes[:4])
            + ("…" if len(p.codes) > 4 else ""),
            "Bajo umbral": "Sí" if p.below_threshold else "—",
        }
        for p in pallets
    ]
    st.dataframe(pd.DataFrame(rows), width="stretch", hide_index=True,
                 height=min(420, 60 + 35 * len(rows)))


def completion_section(plan) -> None:
    """Diagnóstico del sobrante y tabla de qué comprar para completar el contenedor.

    Recibe un ``CompletionPlan`` (analysis.complete_container) y muestra: el % que
    cobraría el sobrante tal cual, qué metales caen bajo el umbral (pagan $0), y la
    pila concreta a comprar —con cuántos kg— para rescatarlos.
    """
    if plan is None or plan.leftover_kg <= 0:
        st.caption("No hay sobrante para analizar.")
        return

    if plan.safe:
        st.success(
            f"El sobrante ({plan.leftover_kg/1000:,.1f} t) ya supera todos los "
            f"umbrales: cobra el **{plan.leftover_util_pct:.0f}%** de su metal sin "
            f"comprar nada. Se puede enviar tal cual.",
            icon=":material/check_circle:",
        )
        return

    below = [g for g in plan.gaps if g.below]
    fragile = [g for g in plan.gaps if g.fragile and not g.below]

    # Encabezado: el sobrante pierde metal bajo el umbral.
    if below:
        nombres = ", ".join(_METAL_NOMBRE.get(g.metal, g.metal) for g in below)
        st.warning(
            f"Si se envía el sobrante tal cual ({plan.leftover_kg/1000:,.1f} t), "
            f"**{nombres}** cae bajo el umbral de la refinería y **paga $0**. "
            f"Aprovecharía solo el **{plan.leftover_util_pct:.0f}%** de su metal.",
            icon=":material/warning:",
        )

    # Recomendación de compra (si hay pila capaz).
    if plan.booster_code and plan.recommend_kg > 0:
        tier = _TIER_NOMBRE.get(plan.booster_tier, plan.booster_tier.lower())
        c1, c2, c3 = st.columns(3)
        c1.metric("Sobrante hoy", f"{plan.leftover_util_pct:.0f}%",
                  help="% del metal del sobrante que la refinería pagaría tal cual.")
        c2.metric("Completando", f"{plan.after_util_pct:.0f}%",
                  delta=f"+{plan.after_util_pct - plan.leftover_util_pct:.0f} pts",
                  help="% del metal del sobrante que se cobra tras mezclar con la "
                       "pila a comprar.")
        c3.metric("Comprar", f"~{plan.recommend_kg:,.0f} kg",
                  delta=f"pila {pile_label(plan.booster_code)}", delta_color="off")
        st.success(
            f"Comprar **~{plan.recommend_kg:,.0f} kg** de la pila "
            f"**{pile_label(plan.booster_code)}** (oro {plan.booster_grade_au:,.0f} "
            f"g/t, ley {tier}) levanta el sobrante por encima del umbral: pasaría de "
            f"**{plan.leftover_util_pct:.0f}%** a **{plan.after_util_pct:.0f}%** de "
            f"su metal cobrado, sin dejar nada en $0.",
            icon=":material/shopping_cart:",
        )

    # Tabla por metal: qué comprar para cada uno.
    rows = []
    for g in below + fragile:
        estado = "Bajo umbral ($0)" if g.below else "Frágil"
        comprar = (f"{pile_label(g.booster_code)} · {g.booster_grade:,.0f} g/t"
                   if g.booster_code else "— sin pila confiable")
        rows.append({
            "Metal": _METAL_NOMBRE.get(g.metal, g.metal),
            "Estado": estado,
            "Ley mezcla": f"{g.grade:,.1f} g/t",
            "Umbral": f"{g.threshold:,.0f} g/t",
            "P. cobro": f"{g.p_cobro*100:.0f}%",
            "Comprar pila": comprar,
            "kg a sumar": f"~{g.add_kg:,.0f}" if g.add_kg > 0 else "—",
        })
    if rows:
        st.caption("Qué comprar, metal por metal (la compra recomendada cubre el "
                   "más exigente):")
        st.dataframe(pd.DataFrame(rows), width="stretch", hide_index=True)

    if plan.unfixable:
        nombres = ", ".join(_METAL_NOMBRE.get(m, m) for m in plan.unfixable)
        st.error(
            f"No hay en el catálogo una pila con ley **confiable** lo bastante rica "
            f"para rescatar **{nombres}**. Hace falta conseguir material rico en "
            f"ese metal (o un ensayo de laboratorio que confirme una pila candidata).",
            icon=":material/error:",
        )


def components_table(components: list[dict], private: bool) -> None:
    """Tabla de pilas que forman un lote (por número, salvo modo privado)."""
    if not components:
        return
    rows = [
        {
            "Pila": pile_label(c["code"], c.get("name", ""), private),
            "kg": round(c.get("kg", 0), 1),
            "Au g/t": c.get("grade_au", 0),
            "Ag g/t": c.get("grade_ag", 0),
            "Cu": c.get("grade_cu", 0),
            "Pd g/t": c.get("grade_pd", 0),
        }
        for c in components
    ]
    st.dataframe(pd.DataFrame(rows), width="stretch", hide_index=True)
