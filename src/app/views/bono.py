"""Bono de éxito — bono por envío, hacia adelante (no sobre el histórico).

El histórico ya se pagó y está cerrado. El bono mira **hacia adelante**: en cada
envío, el sistema rescata metal que pagaría **$0** por caer bajo el umbral (típico
del material de bajo grado que queda en depósito). El bono es **15% de ese metal
rescatado**, por envío, cuando la mejora supera el umbral. Se acumula a medida que
los envíos se ejecutan, y se reconcilia con las liquidaciones reales.
"""

from __future__ import annotations

import copy

import pandas as pd
import streamlit as st

from analysis.bonus import BonusConfig, bono_de_envio
from analysis.complete_container import analyze_completion
from app.data_access import optimizable_items
from app.ui import brand, usd, why
from data.ledger_store import append_entry, clear_ledger, load_ledger
from optimize.optimizer import best_partition

_CONTAINER_KG = 23_000.0
_METAL = {"AU": "oro", "AG": "plata", "PD": "paladio", "PT": "platino"}


def _u(v: float) -> str:
    return usd(v).replace("$", "\\$")


def _cfg() -> BonusConfig:
    return BonusConfig(
        umbral_mejora=float(st.session_state.get("umbral_mejora", 0.10)),
        tasa_bono=float(st.session_state.get("tasa_bono", 0.15)),
        ventana_envios=int(st.session_state.get("ventana_envios", 1)),
    )


def _next_shipment_rescue(prices, terms, k_safe):
    """Próximo envío de material de depósito: arma el contenedor óptimo, toma el
    sobrante (lo que queda para el siguiente envío) y analiza cuánto rescata."""
    items = optimizable_items()
    bp = best_partition(items, prices, terms, max_num_lots=8,
                        container_kg=_CONTAINER_KG, k_safe=k_safe)
    if not bp.result.lots:
        return None
    assigned: dict[str, float] = {}
    for l in bp.result.lots:
        for p in l.components:
            assigned[p.item.code] = assigned.get(p.item.code, 0.0) + p.weight_kg
    leftover = []
    for it in items:
        rem = it.quantity_kg - assigned.get(it.code, 0.0)
        if rem > 1.0:
            c = copy.copy(it)
            c.quantity_kg = rem
            leftover.append(c)
    if not leftover:
        return None
    return analyze_completion(leftover, items, prices, terms, k_safe=k_safe)


def render() -> None:
    prices = st.session_state.prices
    terms = st.session_state.terms
    k_safe = float(st.session_state.get("k_safe", 1.0))
    cfg = _cfg()

    brand(
        "Bono de éxito · por envío",
        "Hacia adelante: en cada envío, 15% del metal que pagaría $0 y el sistema "
        "logra cobrar. El histórico no cuenta — ya se pagó.",
    )
    st.write("")

    # Ledger persistente en disco (registro contractual): sobrevive reinicios.
    ledger = load_ledger()

    # --- Proyección del próximo envío de material de depósito ------------- #
    st.markdown("##### Próximo envío de material de depósito (proyección)")
    st.caption(
        "El material de bajo grado que queda en depósito es donde el sistema "
        "rescata metal: solo, algún metal cae bajo el umbral y paga $0; el sistema "
        "lo hace cobrar al completar/mezclar. Ese metal rescatado es la base del "
        "bono de ese envío."
    )
    if st.button("Calcular el próximo envío", icon=":material/play_arrow:",
                 type="primary"):
        with st.spinner("Armando el contenedor y analizando el sobrante…"):
            st.session_state["bono_envio"] = _next_shipment_rescue(prices, terms, k_safe)

    plan = st.session_state.get("bono_envio")
    if plan is None:
        st.info("Tocá **Calcular el próximo envío** para proyectar el rescate y el "
                "bono de ese envío.")
    elif plan.safe or plan.rescued_usd <= 0:
        st.success(
            "En el próximo envío el material ya supera todos los umbrales: no hay "
            "metal en $0 para rescatar, así que ese envío no genera bono. El bono "
            "aparece cuando el sobrante tiene metal bajo el umbral.",
            icon=":material/check_circle:",
        )
    else:
        be = bono_de_envio(plan.rescued_usd, plan.mejora_pct, cfg)
        riesgo = ", ".join(_METAL.get(g.metal, g.metal) for g in plan.gaps if g.below)
        st.warning(
            f"Sin el sistema, este envío ({plan.leftover_kg/1000:,.1f} t) dejaría "
            f"**{riesgo}** bajo el umbral → pagaría **$0**. El sistema lo rescata "
            f"completando/mezclando.",
            icon=":material/warning:",
        )
        c1, c2, c3 = st.columns(3)
        c1.metric("Metal rescatado", usd(plan.rescued_usd),
                  help="Valor del metal que pagaba $0 y pasa a cobrarse en este envío.")
        c2.metric("Mejora del envío", f"{plan.mejora_pct*100:+.0f}%",
                  delta=f"aprovechado {plan.leftover_util_pct:.0f}% → {plan.after_util_pct:.0f}%",
                  delta_color="off")
        c3.metric("Bono de este envío", usd(be.bono_usd),
                  help="15% del metal rescatado, si la mejora supera el umbral.")
        if be.activado:
            st.success(
                f"La mejora (**{plan.mejora_pct*100:+.0f}%**) supera el "
                f"**{cfg.umbral_mejora*100:.0f}%**: el bono de este envío es "
                f"**{cfg.tasa_bono*100:.0f}% × {_u(plan.rescued_usd)} = "
                f"{_u(be.bono_usd)}**.",
                icon=":material/redeem:",
            )
            if st.button("Registrar este envío como ejecutado", icon=":material/add:"):
                append_entry(plan.rescued_usd, be.bono_usd, plan.mejora_pct)
                st.rerun()
        else:
            st.info(
                f"La mejora (**{plan.mejora_pct*100:+.0f}%**) no supera el "
                f"**{cfg.umbral_mejora*100:.0f}%**: este envío todavía no genera bono.",
                icon=":material/info:",
            )

    # --- Acumulado de envíos ejecutados (persistente en disco) ------------ #
    st.write("")
    st.markdown("##### Acumulado · envíos ejecutados con el modelo")
    if not ledger:
        st.caption("Todavía no registraste envíos ejecutados. A medida que los "
                   "envíos salen, se acumulan acá con su bono — y quedan "
                   "guardados aunque el servidor se reinicie.")
    else:
        df = pd.DataFrame([
            {
                "Envío": f"#{e.get('n', i + 1)}",
                "Fecha": str(e.get("timestamp", ""))[:16].replace("T", " "),
                "Rescatado": e.get("rescatado_usd", 0.0),
                "Bono": e.get("bono_usd", 0.0),
                "Mejora": f"{e.get('mejora_pct', 0.0)*100:+.0f}%",
                "Estado": e.get("estado", "registrado"),
                "Liquidación real": e.get("real_usd"),
            }
            for i, e in enumerate(ledger)
        ])
        st.dataframe(
            df, width="stretch", hide_index=True,
            column_config={
                "Rescatado": st.column_config.NumberColumn(format="$%d"),
                "Bono": st.column_config.NumberColumn(format="$%d"),
                "Liquidación real": st.column_config.NumberColumn(
                    format="$%d",
                    help="Valor de la liquidación real vinculada desde "
                    "Histórico › Cargar liquidación (reconciliación)."),
            },
        )
        st.caption(
            "Los envíos se **reconcilian** desde Histórico › *Cargar liquidación "
            "nueva*, vinculando la liquidación real de la refinería con el envío."
        )
        tot_resc = sum(e.get("rescatado_usd", 0.0) for e in ledger)
        tot_bono = sum(e.get("bono_usd", 0.0) for e in ledger)
        a1, a2, a3 = st.columns(3)
        a1.metric("Envíos registrados", f"{len(ledger)}")
        a2.metric("Metal rescatado acumulado", usd(tot_resc))
        a3.metric("Bono acumulado", usd(tot_bono))
        if st.button("Vaciar acumulado", icon=":material/delete:"):
            clear_ledger()
            st.rerun()

    why(
        "La base es <b>solo el metal que no se hubiese cobrado</b> y que el sistema "
        "rescata, <b>por envío y hacia adelante</b> — no el contenedor completo ni "
        "el histórico (que ya se pagó). Es una proyección sobre leyes estimadas que "
        "<b>se reconcilia</b> con la liquidación real de cada envío. Los parámetros "
        "(umbral, tasa) se editan en <b>Ajustes › Bono</b>.",
        "good",
    )
