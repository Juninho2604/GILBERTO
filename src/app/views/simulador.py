"""Simulador — arma una mezcla a mano y mira el resultado en vivo (Fase 1)."""

from __future__ import annotations

import pandas as pd
import streamlit as st

from app.data_access import inventory_items
from app.ui import brand, pile_label, usd2
from app.views.components import charges_breakdown, lot_header_metrics, metal_table
from domain.models import Category, GradeSource, InventoryItem
from domain.valuation import BlendComponent, value_blend


def _init_df() -> pd.DataFrame:
    items = inventory_items()
    return pd.DataFrame(
        [
            {
                "code": it.code,
                "name": it.name,
                "quantity_kg": round(it.quantity_kg, 1),
                "moisture": it.moisture,
                "grade_cu": round(it.grade_cu, 4),
                "grade_au": round(it.grade_au, 1),
                "grade_ag": round(it.grade_ag, 0),
                "grade_pd": round(it.grade_pd, 1),
                "grade_source": it.grade_source.value,
                "blend_kg": 0.0,
            }
            for it in items
        ]
    )


def _row_to_item(row) -> InventoryItem:
    try:
        source = GradeSource(row["grade_source"])
    except (ValueError, KeyError):
        source = GradeSource.MANUAL
    return InventoryItem(
        code=str(row["code"]),
        name=str(row.get("name", row["code"])),
        category=Category.RAEE,
        quantity_kg=float(row["quantity_kg"]),
        moisture=float(row["moisture"]),
        grade_cu=float(row["grade_cu"]),
        grade_au=float(row["grade_au"]),
        grade_ag=float(row["grade_ag"]),
        grade_pt=0.0,
        grade_pd=float(row["grade_pd"]),
        grade_source=source,
    )


def render() -> None:
    prices = st.session_state.prices
    terms = st.session_state.terms
    private = st.session_state.get("private", False)

    brand("Simulador de mezclas", "Cargá cuánto de cada pila entra y mirá el valor en vivo.")
    st.write("")

    if "sim_df" not in st.session_state:
        st.session_state.sim_df = _init_df()

    # Etiqueta visible (número o número+nombre según modo privado).
    df = st.session_state.sim_df.copy()
    df.insert(0, "Pila", [pile_label(c, n, private) for c, n in zip(df["code"], df["name"])])

    st.markdown("##### Inventario (editable, incluidas las leyes)")
    st.caption(
        "Cu en fracción (0.21 = 21%); Au/Ag/Pd en g/t. **blend_kg** = cuánto de "
        "esa pila entra en la mezcla. Las leyes son estimadas y editables."
    )
    edited = st.data_editor(
        df,
        width="stretch",
        height=360,
        hide_index=True,
        key="sim_editor",
        disabled=["Pila", "code", "name", "grade_source"] if not private else ["Pila", "code", "grade_source"],
        column_config={
            "name": None if not private else st.column_config.TextColumn("name"),
            "code": None,
            "blend_kg": st.column_config.NumberColumn("blend_kg", min_value=0.0, format="%.0f"),
            "grade_source": None,
        },
    )
    # Persistir ediciones (sin la columna calculada "Pila").
    st.session_state.sim_df = edited.drop(columns=["Pila"])

    components: list[BlendComponent] = []
    warnings: list[str] = []
    for _, row in edited.iterrows():
        try:
            blend_kg = float(row.get("blend_kg") or 0.0)
        except (TypeError, ValueError):
            blend_kg = 0.0
        if blend_kg <= 0:
            continue
        item = _row_to_item(row)
        if blend_kg > item.quantity_kg:
            warnings.append(
                f"{pile_label(item.code, item.name, private)}: blend_kg "
                f"({blend_kg:,.0f}) supera el stock ({item.quantity_kg:,.0f} kg)."
            )
        components.append(BlendComponent(item, blend_kg))

    for w in warnings:
        st.warning("⚠️ " + w)

    if not components:
        st.info(
            "Cargá una cantidad en **blend_kg** para una o más pilas. "
            "Tip: usá la pestaña **Optimizador** para que el sistema arme la mezcla solo."
        )
        return

    v = value_blend(components, prices, terms)
    st.markdown("##### Resultado de la mezcla")
    lot_header_metrics(v)
    st.write("")
    col1, col2 = st.columns([1.4, 1])
    with col1:
        metal_table(v)
    with col2:
        charges_breakdown(v)
