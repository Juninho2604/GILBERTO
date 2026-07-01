"""Histórico — cada lote real vs. la mezcla óptima, con su explicación.

Incluye la **carga de liquidaciones nuevas** (el loop de datos): cada
liquidación registrada re-estima las leyes al instante y deja el estudio
completo listo para regenerarse bajo demanda — sin tocar archivos ni redeployar.
"""

from __future__ import annotations

import pandas as pd
import streamlit as st

from app.data_access import history_analysis, history_lot_count, invalidate_caches
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


def _render_cargar_liquidacion() -> None:
    """Formulario para registrar una liquidación real nueva de la refinería."""
    from data.history_store import append_lot, validate_lot
    from data.ledger_store import load_ledger, reconcile_entry
    from data.load_history import load_history

    # Mensaje del guardado anterior (sobrevive el rerun).
    if msg := st.session_state.pop("_liq_msg", None):
        st.success(msg, icon=":material/model_training:")

    with st.expander("Cargar liquidación nueva · el modelo se afina solo",
                     icon=":material/upload_file:"):
        st.caption(
            "Registrá acá cada liquidación que devuelva la refinería: el sistema "
            "re-estima las leyes de las pilas con ese dato **al instante** y "
            "mejora con cada envío. Cu en fracción (0.21 = 21%); el resto en g/t."
        )
        with st.form("nueva_liquidacion"):
            c1, c2, c3, c4 = st.columns(4)
            customer_lot = c1.text_input("Lote (cliente)", placeholder="ej: 95i")
            jx_lot = c2.text_input("Lote JX", placeholder="ej: 2145")
            wmt = c3.number_input("WMT (kg)", min_value=0.0, step=100.0)
            moisture = c4.number_input("Humedad (fracción)", min_value=0.0,
                                       max_value=0.9, value=0.01, step=0.005,
                                       format="%.3f")
            g1, g2, g3, g4, g5 = st.columns(5)
            cu = g1.number_input("Cu (fracción)", min_value=0.0, format="%.4f")
            au = g2.number_input("Au (g/t)", min_value=0.0, step=1.0)
            ag = g3.number_input("Ag (g/t)", min_value=0.0, step=1.0)
            pt = g4.number_input("Pt (g/t)", min_value=0.0, step=1.0)
            pd_g = g5.number_input("Pd (g/t)", min_value=0.0, step=1.0)
            recipe = st.text_input(
                "Receta (por código de pila)",
                placeholder="ej: 1*(28%) + 2*(58%) + 14*(14%)",
                help="La mezcla que formó el lote. Con receta resoluble, la "
                "liquidación además afina las leyes por regresión.",
            )
            # Reconciliación opcional contra un envío registrado en el Bono.
            pendientes = [e for e in load_ledger() if e.get("estado") == "registrado"]
            link_n = None
            if pendientes:
                opts: dict[str, int | None] = {"— no vincular —": None}
                for e in pendientes:
                    opts[f"Envío #{e['n']} ({str(e.get('timestamp', ''))[:10]})"] = e["n"]
                pick = st.selectbox(
                    "¿Corresponde a un envío registrado en el Bono? (reconciliar)",
                    list(opts),
                )
                link_n = opts[pick]
            ok = st.form_submit_button("Registrar liquidación", type="primary",
                                       icon=":material/save:")
        if ok:
            data = {
                "customer_lot": customer_lot, "jx_lot": jx_lot, "wmt": wmt,
                "moisture": moisture, "recipe_raw": recipe,
                "grades": {"CU": cu, "AU": au, "AG": ag, "PT": pt, "PD": pd_g},
            }
            existing_jx = {str(L.jx_lot) for L in load_history() if L.jx_lot}
            errors = validate_lot(data, existing_jx)
            if errors:
                for e in errors:
                    st.error(e, icon=":material/error:")
                return
            append_lot(data)
            if link_n is not None:
                v = value_lot(wmt, moisture, data["grades"],
                              default_prices(), default_terms())
                reconcile_entry(link_n, v.net_value_usd)
            invalidate_caches()
            n = history_lot_count()
            st.session_state["_liq_msg"] = (
                f"Liquidación del lote {customer_lot} registrada. El histórico "
                f"ahora tiene **{n} lotes** y las leyes se re-estimaron con este "
                f"dato." + (" El envío del Bono quedó **reconciliado**."
                            if link_n is not None else "")
            )
            st.rerun()


def render() -> None:
    private = st.session_state.get("private", False)
    a = history_analysis()

    brand(
        "Histórico de lotes",
        f"{a['n_lots']} envíos reales a la refinería · comparados contra la mezcla óptima.",
    )
    st.write("")

    _render_cargar_liquidacion()

    # Estudio precomputado desactualizado: hay liquidaciones nuevas sin analizar.
    live_n = history_lot_count()
    if live_n > a.get("n_lots", 0):
        st.warning(
            f"El estudio de esta página cubre **{a['n_lots']} de {live_n} lotes**: "
            f"hay liquidaciones nuevas que ya afinan las leyes pero aún no entran "
            f"en la comparación real-vs-óptimo. Recalculá para incluirlas.",
            icon=":material/update:",
        )
        if st.button("Recalcular estudio completo ahora (~1–2 min)",
                     icon=":material/refresh:", type="primary"):
            with st.spinner("Re-analizando todos los lotes (corre ~200 "
                            "optimizaciones)…"):
                from analysis.build_analysis import build

                build()
            invalidate_caches()
            st.rerun()
    st.write("")

    c1, c2, c3, c4 = st.columns(4)
    with c1:
        kpi("Material aprovechado", f"{a['util_pct']:.0f}%",
            delta="del metal lo paga la refinería", delta_color=GOOD, accent=True,
            hint="De todo el oro/plata/cobre/paladio presente en los lotes, qué % "
                 "superó los mínimos de la refinería y se cobró.")
    with c2:
        kpi("No aprovechado", f"{a['unused_pct']:.0f}%",
            delta="se pierde bajo el mínimo", delta_color="#e6b451",
            hint="Metal que quedó por debajo del umbral de deducción y pagó $0.")
    with c3:
        kpi("Neto tras cargos", f"{a['net_util_pct']:.0f}%",
            hint="% neto sobre el metal presente, ya descontados tratamiento y "
                 "trituración.")
    with c4:
        kpi("Lotes con receta", f"{a['n_resolvable']}/{a['n_lots']}",
            hint="Resolubles para reconstruir y re-optimizar.")

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
        "**Aprovechado** = del metal presente en el lote, qué % pagó la refinería "
        "(lo que superó sus mínimos); **Neto** descuenta además los cargos. El **$** "
        "queda solo como referencia (leyes medidas, precios de referencia; no es el "
        "efectivo histórico). El bloque **Re-mezcla (est.)** es del mundo estimado y "
        "solo aplica a lotes de **≥2 pilas**. Tocá un lote abajo para el detalle."
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
                "Aprovechado": round(L.get("actual_util_pct", 0)),
                "Neto": round(L.get("actual_net_util_pct", 0)),
                "Valor neto": round(L["actual_net_usd"], 0),
                "USD/kg": round(L["actual_per_kg"], 1),
                "Re-mezcla (est.)": round(L["model_optimal_usd"], 0) if multipila else None,
                "Mejora": round(L["extra_usd"], 0) if (multipila and L["extra_usd"]) else None,
            }
        )
    df = pd.DataFrame(rows)
    st.dataframe(
        df, width="stretch", hide_index=True, height=320,
        column_config={
            "Lote": st.column_config.TextColumn("Lote", help="ID del cliente (puede repetirse entre series)."),
            "JX": st.column_config.TextColumn("JX", help="ID único del envío a la refinería."),
            "Aprovechado": st.column_config.ProgressColumn(
                "Aprovechado", min_value=0, max_value=100, format="%d%%",
                help="% del metal presente que la refinería pagó (superó sus mínimos)."),
            "Neto": st.column_config.NumberColumn(
                "Neto", format="%d%%",
                help="% neto sobre el metal presente, ya descontados los cargos."),
            "Valor neto": st.column_config.NumberColumn(
                "Valor neto ($ ref.)", format="$%.0f",
                help="Referencia en USD (leyes medidas, precios de referencia). No es "
                     "el efectivo histórico."),
            "Re-mezcla (est.)": st.column_config.NumberColumn(
                "Re-mezcla (est.)", format="$%.0f",
                help="MUNDO ESTIMADO: re-partición del material reconstruido con "
                     "leyes estimadas. Solo multipila."),
            "Mejora": st.column_config.NumberColumn(
                "Mejora", format="$%.0f",
                help="Re-mezcla − tal cual, ambos en mundo estimado (comparación honesta)."),
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
    with st.expander("¿Cómo se calcula este precio? (paso a paso)",
                     icon=":material/calculate:", expanded=False):
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
            "Es lo que **pagaría la refinería hoy a estos precios** por esas "
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
