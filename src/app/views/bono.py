"""Bono de éxito — panel del bono definido en el presupuesto (§11).

Muestra las tres piezas: la **base** (sub-pago histórico que el modelo destraba),
el **disparador** (mejora de un envío real por encima del 10%) y el **bono**
(15% de la base, una vez cumplido el disparador). El monto es una estimación que
se reconcilia con los datos reales que vaya devolviendo la refinería.
"""

from __future__ import annotations

import pandas as pd
import streamlit as st

from analysis.bonus import BonusConfig, calcular_bono
from app.data_access import history_analysis
from app.ui import brand, usd, why


def _u(v: float) -> str:
    """USD para texto markdown: escapa el '$' para que no active modo matemático."""
    return usd(v).replace("$", "\\$")


def _cfg() -> BonusConfig:
    return BonusConfig(
        umbral_mejora=float(st.session_state.get("umbral_mejora", 0.10)),
        tasa_bono=float(st.session_state.get("tasa_bono", 0.15)),
        ventana_envios=int(st.session_state.get("ventana_envios", 1)),
    )


def render() -> None:
    cfg = _cfg()

    brand(
        "Bono de éxito",
        "El modelo recupera metal que antes se perdía. Si demuestra una mejora "
        "mayor al umbral en un envío real, se activa el bono.",
    )
    st.write("")

    analysis = history_analysis()
    lots = analysis.get("lots", [])

    # --- Registro de envíos reales ejecutados con el modelo (el disparador) --- #
    st.markdown("##### Envío(s) real(es) ejecutado(s) con el modelo")
    st.caption(
        f"La mejora se mide sobre los primeros **{cfg.ventana_envios}** envío(s) "
        f"(promediados, para que el ruido del ensayo no la distorsione). Cargá, por "
        f"cada envío: lo que **pagó la refinería** (real) y lo que ese material "
        f"habría rendido **sin optimizar** (mezcla ingenua)."
    )
    envios = []
    for i in range(1, cfg.ventana_envios + 1):
        c1, c2 = st.columns(2)
        vm = c1.number_input(
            f"Envío {i} · pagó la refinería (USD)", min_value=0.0, value=0.0,
            step=1000.0, key=f"bono_vm_{i}",
            help="Valor real de la liquidación del envío optimizado.",
        )
        vb = c2.number_input(
            f"Envío {i} · sin optimizar (USD)", min_value=0.0, value=0.0,
            step=1000.0, key=f"bono_vb_{i}",
            help="Contrafáctico: lo que ese mismo material habría rendido con la "
            "mezcla anterior (proyección del modelo).",
        )
        if vb > 0:
            envios.append((vm, vb))

    res = calcular_bono(lots, envios, cfg)
    sp = res.subpago
    mj = res.mejora

    # --- 1) La base: sub-pago histórico, descompuesto con honestidad ------ #
    st.markdown("##### Base · sub-pago histórico (lo que el modelo destraba)")
    b1, b2, b3 = st.columns(3)
    b1.metric("Sub-pago histórico", usd(sp.total_usd),
              help="Σ de (óptimo − real) sobre los lotes del histórico, a los "
              "mismos precios por lote. Definición del change-order (§3.1).")
    b2.metric("Ganancia de mezcla verificable", usd(sp.mixing_usd),
              help="Óptimo − 'tal cual', ambos en el mundo estimado: el efecto "
              "real del optimizador, sin mezclar mundos.")
    b3.metric("Brecha de proyección", usd(sp.projection_usd),
              delta="se reconcilia con datos reales", delta_color="off",
              help="Diferencia entre la valorización estimada y el pago medido "
              "real. No es dinero asegurado: se ajusta con cada liquidación.")
    st.warning(
        f"**Lectura honesta de la base.** De los {_u(sp.total_usd)}, solo "
        f"**{_u(sp.mixing_usd)}** son ganancia de mezcla **verificable** (mismo "
        f"mundo); los **{_u(sp.projection_usd)}** restantes son la **brecha** "
        f"entre la valorización estimada del modelo y el pago real medido — "
        f"proyección que **se reconcilia** contra las liquidaciones reales. "
        f"Conviene acordar (decisión de negocio §5) si el bono se liquida sobre la "
        f"proyección o reconciliado contra el dato real.",
        icon=":material/balance:",
    )
    st.caption(
        f"Confianza por pila: el **{sp.low_conf_share*100:.0f}%** de la base se "
        f"apoya en pilas de baja confianza; piso firme **{_u(sp.firm_usd)}**."
    )
    if sp.lots:
        top = sp.lots[:10]
        df = pd.DataFrame([
            {"Lote": str(r.customer_lot),
             "Pagó la refinería": round(r.valor_real_usd, 0),
             "Óptimo del modelo": round(r.valor_optimo_usd, 0),
             "Sub-pago": round(r.sub_pago_usd, 0),
             "Baja conf.": f"{r.low_conf_share*100:.0f}%"}
            for r in top
        ])
        st.caption("Lotes que más aportan a la base:")
        st.dataframe(
            df, width="stretch", hide_index=True,
            column_config={
                "Pagó la refinería": st.column_config.NumberColumn(format="$%d"),
                "Óptimo del modelo": st.column_config.NumberColumn(format="$%d"),
                "Sub-pago": st.column_config.NumberColumn(format="$%d"),
            },
        )

    # --- 2) El disparador: mejora del envío ------------------------------- #
    st.markdown("##### Disparador · mejora del envío real")
    if mj is None:
        st.info(
            f"Aún no hay envíos ejecutados con el modelo. El bono se activa cuando "
            f"un envío real demuestre una mejora mayor al "
            f"**{cfg.umbral_mejora*100:.0f}%** (por encima del ruido del ensayo).",
            icon=":material/hourglass_empty:",
        )
    else:
        d1, d2, d3 = st.columns(3)
        d1.metric("Mejora medida", f"{mj.mejora*100:+.1f}%",
                  help="(pagó la refinería − sin optimizar) / sin optimizar.")
        d2.metric("Umbral", f"{cfg.umbral_mejora*100:.0f}%")
        d3.metric("Envíos usados", f"{mj.n_envios}")
        if mj.supera_umbral:
            st.success(
                f"La mejora (**{mj.mejora*100:+.1f}%**) supera el umbral de "
                f"**{cfg.umbral_mejora*100:.0f}%**: es demasiado grande para ser "
                f"ruido del ensayo → atribuible al modelo. **Disparador cumplido.**",
                icon=":material/check_circle:",
            )
        else:
            st.warning(
                f"La mejora (**{mj.mejora*100:+.1f}%**) no supera el umbral de "
                f"**{cfg.umbral_mejora*100:.0f}%**: dentro del ruido natural del "
                f"ensayo, todavía no atribuible al modelo con confianza.",
                icon=":material/info:",
            )

    # --- 3) El bono ------------------------------------------------------- #
    st.markdown("##### El bono")
    if res.activado:
        st.markdown(f"### Bono activado · {_u(res.monto_usd)}")
        st.caption(
            f"**{cfg.tasa_bono*100:.0f}%** de la base de **{_u(res.base_usd)}**. "
            f"Banda: entre **{_u(res.monto_firme_usd)}** (sobre el piso de alta "
            f"confianza) y **{_u(res.monto_usd)}** (sobre la base puntual)."
        )
    else:
        st.markdown("### Bono no activado")
        st.caption(
            f"Cuando un envío real supere el **{cfg.umbral_mejora*100:.0f}%** de "
            f"mejora, el bono sería **{cfg.tasa_bono*100:.0f}% × "
            f"{_u(res.base_usd)} = {_u(cfg.tasa_bono * res.base_usd)}** "
            f"(estimación sobre la base actual)."
        )

    why(
        "El monto es una <b>estimación</b> calculada por el propio modelo a partir "
        "de leyes estimadas: el lado <b>real</b> usa las liquidaciones medidas "
        "(alta confianza) y el <b>óptimo/ingenuo</b> son proyección. Se "
        "<b>reconcilia</b> con los datos reales que devuelva la refinería en cada "
        "envío. Los parámetros (umbral, tasa, ventana) se editan en <b>Ajustes</b>.",
        "good",
    )
