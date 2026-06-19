"""Componentes compartidos por las vistas (tablas de lote, explicaciones)."""

from __future__ import annotations

import pandas as pd
import streamlit as st

from app.ui import pile_label, pill, usd, usd2, why
from domain.models import METALS
from domain.valuation import LotValuation

_ROLE_LABEL = {"rico": "LOTE RICO", "relleno": "RELLENO", "mixto": "MIXTO"}


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
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Valor neto", usd2(v.net_value_usd))
    c2.metric("USD / kg", f"{v.result_per_kg:,.2f}")
    c3.metric("WMT", f"{v.wmt:,.0f} kg")
    c4.metric("Au mezcla", f"{v.metals['AU'].grade:,.0f} g/t")


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
