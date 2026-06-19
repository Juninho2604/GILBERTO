"""Caso de negocio — cuantifica el valor del sistema para fijarle precio."""

from __future__ import annotations

import streamlit as st

from app.data_access import default_optimum, history_analysis
from app.ui import GOOD, MUTED, brand, kpi, usd, why


def render() -> None:
    a = history_analysis()
    opt = default_optimum()

    brand(
        "Caso de negocio",
        "Cuánto vale el optimizador — para proyectar el precio del sistema.",
    )
    st.write("")

    st.markdown(
        "El valor del sistema tiene **tres fuentes**: optimización por envío, "
        "rescate de metal sub-umbral y la reducción de riesgo/tiempo en cada "
        "decisión. Abajo se proyecta sobre el volumen histórico real."
    )
    st.write("")

    # --- Parámetros del usuario ------------------------------------------- #
    c1, c2, c3 = st.columns(3)
    annual_throughput = c1.number_input(
        "Pago anual a la refinería (USD)",
        value=float(round(a["actual_total_usd"], -3)),
        step=50_000.0,
        help="Por defecto, el total pagado en el histórico cargado.",
    )
    gain_pct = c2.number_input(
        "Mejora por optimización (%)",
        value=float(round(opt["gain_vs_single_pct"], 2)),
        step=0.1,
        help="Por defecto, lo que gana la mejor partición vs. una sola mezcla "
        "sobre el stock actual.",
    )
    capture = c3.slider(
        "Fracción capturada (%)", 0, 100, 60,
        help="Qué parte de la mejora teórica se logra en la práctica (conservador).",
    )

    annual_gain = annual_throughput * (gain_pct / 100.0) * (capture / 100.0)
    rescue = a["sub_threshold_total_usd"]
    total_value = annual_gain + rescue

    st.write("")
    k1, k2, k3 = st.columns(3)
    with k1:
        kpi("Valor optimización / año", usd(annual_gain),
            delta=f"{gain_pct:.1f}% × {capture}% captura", delta_color=GOOD,
            hint="Sobre el pago anual proyectado.", accent=True)
    with k2:
        kpi("Metal rescatable", usd(rescue),
            delta="Ag/Pd sub-umbral", delta_color="#e6b451",
            hint="Detectado en el histórico; recurrente si se repite el patrón.")
    with k3:
        kpi("Valor cuantificable / año", usd(total_value),
            hint="Piso 'duro' para anclar el precio (no incluye tiempo ni riesgo).")

    st.write("")

    # --- Sugerencia de precio --------------------------------------------- #
    st.markdown("##### Cómo fijar el precio (sugerencia)")
    share = st.slider(
        "Participación del proveedor sobre el valor generado (%)", 5, 50, 25,
        help="Modelo típico de software de optimización: el proveedor cobra una "
        "fracción del valor que crea.",
    )
    annual_price = total_value * (share / 100.0)
    p1, p2 = st.columns(2)
    with p1:
        kpi("Precio anual sugerido", usd(annual_price),
            delta=f"{share}% del valor generado", delta_color=MUTED, accent=True)
    with p2:
        kpi("Equivalente mensual", usd(annual_price / 12.0),
            hint="Como suscripción (SaaS).")

    st.write("")
    why(
        "<b>Argumento honesto para Gilberto:</b> el modelo es fiel a su realidad "
        f"(±{a['money_fidelity_pct']:.1f}%) y respeta su criterio (sus lotes ya eran "
        f"casi óptimos). El sistema no promete milagros: paga su precio capturando "
        f"un {gain_pct:.1f}% por envío del stock acumulado, rescatando metal que hoy "
        "se pierde, y dándole una herramienta para decidir en segundos en vez de a mano.",
        "good",
    )
    why(
        "<b>Valor no cuantificado aquí</b> (suma sobre lo anterior): simulación "
        "instantánea de escenarios, explicación auditable de cada decisión, "
        "trazabilidad de leyes (estimada vs. laboratorio) y menos riesgo de un "
        "envío mal armado.",
    )

    st.write("")
    st.info(
        "Cifras basadas en **leyes estimadas** y en los términos de contrato "
        "actuales. Validar las leyes con laboratorio y confirmar los términos (§7) "
        "ajustará estos números — probablemente al alza para las pilas ricas.",
        icon="ℹ️",
    )
