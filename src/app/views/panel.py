"""Panel — resumen ejecutivo: precisión del modelo y valor del optimizador."""

from __future__ import annotations

import streamlit as st

from app.data_access import default_optimum, history_analysis
from app.ui import GOOD, MUTED, brand, kpi, usd, why


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
            "Material aprovechado — stock actual",
            f"{opt['best_util_pct']:.0f}%",
            delta="del metal lo paga la refinería",
            delta_color=GOOD,
            accent=True,
            hint=f"Mejor mezcla del stock con ley ({opt['n_graded']} pilas · "
            f"{opt['graded_stock_kg']:,.0f} kg). El resto cae bajo los mínimos.",
        )
    with c3:
        kpi(
            "Gana vs. mezcla única",
            f"+{opt['gain_vs_single_pct']:.1f}%",
            delta="por mezclar mejor (no diluir el oro)",
            delta_color=GOOD,
            hint="Separar lo rico del relleno rinde más que mezclar todo junto.",
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
            f"<b>Agrega valor hacia adelante.</b> Sobre el stock <b>actual</b> "
            f"(aún sin enviar), la mejor partición paga <b>+{usd(opt['gain_vs_single_usd'])}</b> "
            f"({opt['gain_vs_single_pct']:+.1f}%) frente a una sola mezcla, y "
            f"<b>+{usd(opt['gain_vs_best_simple_usd'])}</b> frente a enviar todo por separado.",
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
    st.info(
        "Las leyes son **estimadas** desde el histórico y están a validar con "
        "ensayos reales. Preguntas abiertas (§7) que mueven el óptimo: tamaño "
        "mínimo de lote, si el platino se paga, y si los términos son negociados.",
        icon="ℹ️",
    )


def _au_err(a: dict) -> float:
    for p in a["precision"]:
        if p["metal"] == "AU":
            return p["median_abs_err_pct"]
    return 0.0
