"""Histórico — cada lote real vs. la mezcla óptima, con su explicación."""

from __future__ import annotations

import pandas as pd
import streamlit as st

from app.data_access import history_analysis
from app.ui import GOOD, brand, kpi, usd, why
from app.views.components import (
    charges_breakdown,
    components_table,
    explanation_block,
    lot_header_metrics,
    metal_table,
)
from domain.models import default_prices, default_terms
from domain.valuation import value_lot

_METAL_NAME = {"AU": "oro", "AG": "plata", "PD": "paladio", "PT": "platino"}


def render() -> None:
    private = st.session_state.get("private", False)
    a = history_analysis()

    brand(
        "Histórico de lotes",
        f"{a['n_lots']} envíos reales a la refinería · comparados contra la mezcla óptima.",
    )
    st.write("")

    c1, c2, c3, c4 = st.columns(4)
    with c1:
        kpi("Valorización total (medida)", usd(a["actual_total_usd"]),
            hint="Fórmula §3 sobre las leyes MEDIDAS de cada lote, a precios de "
                 "referencia. No es el efectivo histórico (los precios variaban).")
    with c2:
        kpi("Lotes con receta", f"{a['n_resolvable']}/{a['n_lots']}",
            hint="Resolubles para reconstruir y re-optimizar.")
    with c3:
        kpi("Mejora re-mezclando", f"+{a['extra_pct']:.1f}%",
            delta=f"+{usd(a['extra_usd'])}", delta_color=GOOD,
            hint="Solo lotes multipila, mundo estimado vs. estimado. Las mezclas "
                 "históricas ya eran casi óptimas.")
    with c4:
        kpi("Metal sub-umbral", usd(a["sub_threshold_total_usd"]),
            delta="pagó $0", delta_color="#e6b451",
            hint="Ag/Pd bajo el umbral de deducción.")

    st.write("")
    why(
        "Este histórico es la <b>prueba de fidelidad</b> de las leyes estimadas: "
        "reconstruidas, reproducen la <b>valorización medida</b> con "
        f"±{a['money_fidelity_pct']:.1f}% de desvío (estimado vs. medido, mismos "
        "precios). Y al re-mezclar los lotes multipila, la mejora posible es de "
        f"solo +{a['extra_pct']:.1f}%: las decisiones de Gilberto ya eran muy "
        "buenas. El margen grande está hacia adelante, sobre el stock acumulado "
        "(ver Optimizador).",
        "good",
    )
    st.write("")

    # --- Tabla resumen ----------------------------------------------------- #
    st.markdown("##### Lote por lote")
    st.caption(
        "Hay **dos mundos, no comparables 1:1**. **Valorización medida** = fórmula "
        "§3 sobre las leyes **medidas** por la refinería (a precios de referencia). "
        "El bloque **Re-mezcla (estimado)** reconstruye las pilas con leyes "
        "**estimadas** y deja que el optimizador re-particione: solo tiene sentido "
        "en lotes de **≥2 pilas** (en monopila no hay nada que mezclar, va '—'). "
        "La columna honesta es **Mejora** (estimado vs. estimado, mismo mundo). "
        "Tocá un lote abajo para ver el cálculo paso a paso."
    )
    rows = []
    for L in a["lots"]:
        # La re-mezcla solo tiene sentido con ≥2 pilas resolubles.
        multipila = L["n_components"] > 1 and L["model_optimal_usd"] is not None
        rows.append(
            {
                "Lote": str(L["customer_lot"]),
                "JX": str(L["jx_lot"]),
                "Receta": _mask_recipe(L["recipe_raw"], private),
                "kg": round(L["wmt"], 0),
                "Valorización medida": round(L["actual_net_usd"], 0),
                "USD/kg": round(L["actual_per_kg"], 1),
                "Re-mezcla (est.)": round(L["model_optimal_usd"], 0) if multipila else None,
                "Mejora": round(L["extra_usd"], 0) if (multipila and L["extra_usd"]) else None,
                "Sub-umbral": round(sum(s["gross_value_usd"] for s in L["sub_threshold"]), 0) or None,
            }
        )
    df = pd.DataFrame(rows)
    st.dataframe(
        df, width="stretch", hide_index=True, height=320,
        column_config={
            "Lote": st.column_config.TextColumn("Lote", help="ID del cliente (puede repetirse entre series)."),
            "JX": st.column_config.TextColumn("JX", help="ID único del envío a la refinería."),
            "Valorización medida": st.column_config.NumberColumn(
                "Valorización medida", format="$%.0f",
                help="Leyes medidas, precios de referencia. No es el efectivo histórico."),
            "Re-mezcla (est.)": st.column_config.NumberColumn(
                "Re-mezcla (est.)", format="$%.0f",
                help="MUNDO ESTIMADO: re-partición del material reconstruido con "
                     "leyes estimadas. Solo multipila. No comparable 1:1 con la "
                     "valorización medida."),
            "Mejora": st.column_config.NumberColumn(
                "Mejora", format="$%.0f",
                help="Re-mezcla − tal cual, ambos en mundo estimado (comparación honesta)."),
            "Sub-umbral": st.column_config.NumberColumn(
                "Metal $0", format="$%.0f",
                help="Ag/Pd bajo el umbral de deducción: pagó $0 (leyes medidas)."),
        },
    )

    # --- Detalle de un lote ----------------------------------------------- #
    st.markdown("##### Detalle de un lote")
    resolvable = [L for L in a["lots"] if L.get("explanation")]
    options = {
        f"Lote {L['customer_lot']} · {_mask_recipe(L['recipe_raw'], private)} "
        f"({usd(L['actual_net_usd'])})": L
        for L in sorted(resolvable, key=lambda x: -(x["extra_usd"] or 0))
    }
    if not options:
        return
    pick = st.selectbox("Elegí un lote resoluble", list(options.keys()))
    L = options[pick]

    m1, m2, m3 = st.columns(3)
    m1.metric("Valorización (medida)", usd(L["actual_net_usd"]),
              help="Leyes medidas, precios de referencia (no efectivo histórico).")
    m2.metric("Modelo 'tal cual' (est.)", usd(L["model_aswas_usd"] or 0),
              help="Leyes estimadas, mezcla como la armó Gilberto.")
    m3.metric("Modelo re-mezcla (est.)", usd(L["model_optimal_usd"] or 0),
              delta=f"+{usd(L['extra_usd'] or 0)}",
              help="Leyes estimadas, mejor partición. Mejora = vs. 'tal cual'.")

    # --- Transparencia: cómo se calcula el $ de este lote ------------------ #
    with st.expander("🧮 ¿Cómo se calcula este precio? (paso a paso)", expanded=False):
        prices, terms = default_prices(), default_terms()
        v = value_lot(
            wmt=L["wmt"], moisture=L["moisture"],
            grades=L["actual_grades"], prices=prices, terms=terms,
        )
        st.caption(
            f"Se aplica la **fórmula de la refinería (§3)** sobre las **leyes "
            f"medidas** del lote, a **precios de referencia**. Peso húmedo "
            f"WMT = {L['wmt']:,.0f} kg; seco DMT = WMT×(1−humedad) = "
            f"{v.dmt:,.0f} kg. Para cada metal: contenido → se descuenta la "
            f"deducción por tonelada (recuperación RR) → se valoriza al precio "
            f"menos el cargo de refinación. Al final se restan los cargos por peso."
        )
        lot_header_metrics(v)
        st.write("")
        cc1, cc2 = st.columns([1.4, 1])
        with cc1:
            st.caption("Metal por metal (medido)")
            metal_table(v)
        with cc2:
            st.caption("Metal total − cargos")
            charges_breakdown(v)
        st.caption(
            "⚠️ Es lo que **pagaría la refinería hoy a estos precios** por esas "
            "leyes; no necesariamente lo que se pagó el día del envío (los "
            "precios varían). Cambiá los precios en la barra lateral para otro "
            "escenario del Simulador."
        )

    st.caption("Pilas que formaron el lote (reconstruidas desde la receta)")
    components_table(L["components"], private)

    if L["sub_threshold"]:
        for s in L["sub_threshold"]:
            why(
                f"<b>{_METAL_NAME.get(s['metal'], s['metal']).capitalize()}</b>: "
                f"ley {s['grade']:.1f} g/t, por debajo del umbral de "
                f"{s['threshold']:.0f} g/t → pagó <b>$0</b>. Hay "
                f"{s['content_g']:.0f} g presentes (≈ {usd(s['gross_value_usd'])} a "
                f"spot) que mezclando con una pila rica se cobrarían.",
                "warn",
            )

    st.markdown("**Por qué la partición óptima es mejor**")
    explanation_block(L["explanation"])


def _mask_recipe(recipe: str, private: bool) -> str:
    """La receta ya usa números (1, 2, 14…), que es la leyenda de Gilberto.

    En modo no privado se muestra tal cual (son números, no nombres). Si fuese
    texto libre con nombres de cliente, se enmascara.
    """
    if not recipe:
        return "—"
    # Heurística: si contiene letras (texto libre), ocultar salvo modo privado.
    has_alpha = any(ch.isalpha() for ch in recipe)
    if has_alpha and not private:
        return "(receta con texto)"
    return recipe
