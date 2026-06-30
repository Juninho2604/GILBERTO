"""Bono de éxito — panel del bono definido en el presupuesto (§11).

La **base** es el *rescate demostrado*: el metal que la mezcla "tal cual" dejaba
en $0 (bajo umbral) y que el optimizador logra cobrar. El **disparador** es la
mejora de un envío real por encima del umbral. El **bono** es 15% de la base.
El monto es una estimación que se reconcilia con los datos reales de la refinería.
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
        "El bono se calcula sobre el material que no se hubiese cobrado y que el "
        "optimizador logra cobrar — no sobre el contenedor completo.",
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
    rc = res.rescate
    mj = res.mejora

    # --- 1) La base: rescate demostrado ----------------------------------- #
    st.markdown("##### Base · material rescatado del umbral (lo que el modelo cobra)")
    b1, b2, b3 = st.columns(3)
    b1.metric("Rescate demostrado", usd(rc.total_usd),
              help="Metal que la mezcla 'tal cual' dejaba en $0 por caer bajo el "
              "umbral, y que el optimizador logra cobrar. Mismo mundo (leyes "
              "estimadas): aísla el efecto del optimizador, sin sesgo.")
    b2.metric("Piso de alta confianza", usd(rc.firm_usd),
              help="Porción del rescate que NO depende de pilas de baja confianza.")
    b3.metric("Lotes que aportan", f"{rc.n_lots}",
              delta=f"{rc.low_conf_share*100:.0f}% en pilas frágiles",
              delta_color="off")
    st.caption(
        f"La base es **{_u(rc.total_usd)}** (no el contenedor completo): solo el "
        f"metal sub-umbral que el optimizador rescata respecto al método actual. "
        f"Históricamente es chico porque **las mezclas de Gilberto ya eran muy "
        f"buenas** — el grueso del rescate está hacia adelante, optimizando todo el "
        f"inventario acumulado."
    )
    if rc.lots:
        df = pd.DataFrame([
            {"Lote": str(r.customer_lot),
             "Rescatado": round(r.rescatado_usd, 0),
             "Baja conf.": f"{r.low_conf_share*100:.0f}%"}
            for r in rc.lots[:10]
        ])
        st.caption("Lotes donde el optimizador rescata metal sub-umbral:")
        st.dataframe(
            df, width="stretch", hide_index=True,
            column_config={"Rescatado": st.column_config.NumberColumn(format="$%d")},
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
            f"**{cfg.tasa_bono*100:.0f}%** de la base de **{_u(res.base_usd)}** "
            f"(material rescatado). Banda: entre **{_u(res.monto_firme_usd)}** "
            f"(piso de alta confianza) y **{_u(res.monto_usd)}** (base puntual)."
        )
    else:
        st.markdown("### Bono no activado")
        st.caption(
            f"Cuando un envío real supere el **{cfg.umbral_mejora*100:.0f}%** de "
            f"mejora, el bono sería **{cfg.tasa_bono*100:.0f}% × "
            f"{_u(res.base_usd)} = {_u(cfg.tasa_bono * res.base_usd)}** "
            f"(15% del material rescatado, estimación sobre la base actual)."
        )

    why(
        "La base es <b>solo el material que no se hubiese cobrado</b> y que el "
        "optimizador rescata — no el contenedor completo. Es una <b>estimación</b> "
        "en el mundo de leyes estimadas que <b>se reconcilia</b> con los datos "
        "reales de cada liquidación. Los parámetros (umbral, tasa, ventana) se "
        "editan en <b>Ajustes › Bono</b>.",
        "good",
    )
