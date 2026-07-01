"""Panel — resumen ejecutivo: precisión del modelo y valor del optimizador."""

from __future__ import annotations

import pandas as pd
import streamlit as st

from app.data_access import default_optimum, history_analysis
from app.ui import GOOD, brand, kpi, usd, why


def render() -> None:
    brand(
        "Optimizador de Mezclas RAEE",
        "Servicios Megabytes, C.A. · panel de control del modelo de valorización y mezcla.",
    )
    st.write("")

    a = history_analysis()
    opt = default_optimum()

    # --- Fila 1: precisión y valor ---------------------------------------- #
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        kpi(
            "Precisión del modelo",
            f"±{a['money_fidelity_pct']:.1f}%",
            delta="vs. pago real de la refinería",
            delta_color=GOOD,
            hint=f"Sobre {a['n_resolvable']} lotes históricos reconstruidos.",
            accent=True,
        )
    with c2:
        kpi(
            "Material aprovechado — próximo contenedor",
            f"{opt['best_util_pct']:.0f}%",
            delta="del metal lo paga la refinería",
            delta_color=GOOD,
            accent=True,
            hint=f"Mejor contenedor de {opt['container_kg']/1000:,.0f} t "
            f"({opt['container_weight_kg']/1000:,.1f} t, {opt['container_fill_pct']:.0f}% "
            f"lleno) armado desde el stock con ley.",
        )
    with c3:
        kpi(
            "Envíos pendientes",
            f"~{opt['n_envios']}",
            delta="1 contenedor cada ~3 meses",
            delta_color=GOOD,
            hint=f"Con {opt['graded_stock_kg']:,.0f} kg en stock y "
            f"{opt['container_kg']/1000:,.0f} t por contenedor.",
        )
    with c4:
        kpi(
            "Material desaprovechado — histórico",
            f"{a['unused_pct']:.0f}%",
            delta="metal que pagó $0 bajo el mínimo",
            delta_color="#e6b451",
            hint="Promedio sobre los 53 lotes: metal presente que no superó el "
            "umbral de deducción.",
        )

    st.write("")

    # --- Bloque explicativo ------------------------------------------------ #
    left, right = st.columns([1.15, 1])
    with left:
        st.markdown("##### ¿Qué demuestra este modelo?")
        why(
            f"<b>Es fiel a la realidad.</b> Reconstruido sobre {a['n_resolvable']} "
            f"lotes históricos, reproduce el dinero que pagó la refinería con un "
            f"desvío de solo <b>{a['money_fidelity_pct']:.1f}%</b>. Las leyes "
            f"estimadas aciertan el oro con ~{_au_err(a):.0f}% de error mediano.",
            "good",
        )
        why(
            f"<b>Confirma el buen criterio histórico.</b> Re-optimizar cada lote "
            f"que ya envió Gilberto solo agrega +{a['extra_pct']:.1f}%: sus mezclas "
            f"ya eran casi óptimas. El modelo no lo contradice, lo respalda.",
        )
        why(
            f"<b>Optimiza el próximo envío.</b> Sobre el stock <b>actual</b>, arma "
            f"el mejor <b>contenedor de {opt['container_kg']/1000:,.0f} t</b> que "
            f"cobra el <b>{opt['best_util_pct']:.0f}%</b> del metal cargado, dejando "
            f"el resto del stock para los siguientes envíos.",
            "good",
        )
        why(
            f"<b>Evita perder metal.</b> Detecta plata y paladio que históricamente "
            f"pagaron $0 por quedar bajo el umbral de deducción "
            f"(<b>{usd(a['sub_threshold_total_usd'])}</b> en total): material que, "
            f"mezclado, se cobra.",
            "warn",
        )

    with right:
        st.markdown("##### Cobertura de datos")
        cov = a["coverage"]
        st.metric("Pilas con ley estimada", f"{cov['covered']}/{cov['stocked_items']}")
        st.progress(cov["covered"] / max(cov["stocked_items"], 1))
        st.caption(
            f"{cov['pending']} pilas sin receta en el histórico → pendientes de "
            f"ensayo de laboratorio o carga manual."
        )
        st.markdown("##### Validación por metal")
        for p in a["precision"]:
            st.caption(
                f"**{p['metal']}** · error mediano {p['median_abs_err_pct']:.1f}% "
                f"(n={p['n']})"
            )

    st.write("")

    # --- Evolución del modelo (cadencia trimestral) ------------------------ #
    _render_evolucion(a)

    st.write("")
    st.info(
        "Las leyes son **estimadas** desde el histórico y están a validar con "
        "ensayos reales. Preguntas abiertas (§7) que mueven el óptimo: tamaño "
        "mínimo de lote, si el platino se paga, y si los términos son negociados.",
        icon=":material/info:",
    )


def _render_evolucion(a: dict) -> None:
    """El modelo en el tiempo: cada recalculado del estudio deja una foto y acá
    se ve si mejora — el argumento medible de que el sistema vale más cada
    trimestre que se usa."""
    from data.snapshots import load_snapshots, record_snapshot

    # Baseline automático: la primera visita registra el estado actual.
    snaps = load_snapshots()
    if not snaps:
        record_snapshot(a)
        snaps = load_snapshots()

    st.markdown("##### Evolución del modelo")
    if len(snaps) < 2:
        s = snaps[-1] if snaps else None
        st.caption(
            "Primer registro tomado"
            + (f" ({str(s['timestamp'])[:10]}): error de dinero "
               f"**±{s['money_fidelity_pct']:.1f}%** con **{s['n_lots']} lotes** "
               f"y **{s['coverage_covered']}/{s['coverage_stocked']}** pilas con ley. "
               if s else ". ")
            + "Cada liquidación nueva que cargues (Histórico) y cada recalculado "
              "del estudio agregan una foto: acá vas a ver si el modelo mejora."
        )
        return

    prev, cur = snaps[-2], snaps[-1]
    d_fid = cur["money_fidelity_pct"] - prev["money_fidelity_pct"]
    d_lots = cur["n_lots"] - prev["n_lots"]
    d_au = cur["err_pct"].get("AU", 0.0) - prev["err_pct"].get("AU", 0.0)
    e1, e2, e3 = st.columns(3)
    e1.metric(
        "Error de dinero (estimado vs. real)",
        f"±{cur['money_fidelity_pct']:.1f}%",
        delta=f"{d_fid:+.1f} pts vs. registro anterior",
        delta_color="inverse",  # menos error = verde
    )
    e2.metric(
        "Error mediano en oro",
        f"{cur['err_pct'].get('AU', 0.0):.1f}%",
        delta=f"{d_au:+.1f} pts", delta_color="inverse",
    )
    e3.metric(
        "Lotes que alimentan el modelo",
        f"{cur['n_lots']}",
        delta=f"+{d_lots} liquidación(es)" if d_lots > 0 else "sin lotes nuevos",
        delta_color="off",
    )
    if d_fid < 0 or d_au < 0:
        st.caption(
            f"**El modelo mejoró con tus datos**: el error pasó de "
            f"±{prev['money_fidelity_pct']:.1f}% a ±{cur['money_fidelity_pct']:.1f}% "
            f"entre {str(prev['timestamp'])[:10]} y {str(cur['timestamp'])[:10]}. "
            f"Se afina solo: cada liquidación cargada lo calibra."
        )
    hist = pd.DataFrame([
        {
            "Fecha": str(s["timestamp"])[:10],
            "Lotes": s["n_lots"],
            "Error $ (%)": s["money_fidelity_pct"],
            "Error Au (%)": s["err_pct"].get("AU", 0.0),
            "Error Ag (%)": s["err_pct"].get("AG", 0.0),
            "Pilas con ley": f"{s['coverage_covered']}/{s['coverage_stocked']}",
        }
        for s in snaps[-8:]
    ])
    st.dataframe(hist, width="stretch", hide_index=True)


def _au_err(a: dict) -> float:
    for p in a["precision"]:
        if p["metal"] == "AU":
            return p["median_abs_err_pct"]
    return 0.0
