"""Inventario — editar y cargar stock en tiempo real (fuente de verdad).

El usuario puede editar cantidades y leyes, agregar pilas nuevas, o **cargar un
``.xlsx``** de inventario. Al guardar, el estado se persiste en el servidor y
todos los módulos (Simulador, Optimizador, Panel) pasan a usarlo.
"""

from __future__ import annotations

import pandas as pd
import streamlit as st

from app.data_access import inventory_items, invalidate_caches
from app.ui import brand, pile_label, usd
from data.inventory_store import has_saved_state, reset_state, save_state
from domain.models import Category, GradeSource, InventoryItem

_COLS = [
    "code", "name", "quantity_kg", "moisture",
    "grade_cu", "grade_au", "grade_ag", "grade_pd", "grade_source",
]


def _items_to_df(items: list[InventoryItem], private: bool) -> pd.DataFrame:
    df = pd.DataFrame(
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
            }
            for it in items
        ]
    )
    df.insert(0, "Pila", [pile_label(c, n, private) for c, n in zip(df["code"], df["name"])])
    return df


def _df_to_items(df: pd.DataFrame) -> list[InventoryItem]:
    items: list[InventoryItem] = []
    for _, row in df.iterrows():
        code = str(row.get("code") or "").strip()
        if not code or code.lower() == "nan":
            continue
        try:
            source = GradeSource(row.get("grade_source", "manual"))
        except (ValueError, KeyError):
            source = GradeSource.MANUAL
        try:
            items.append(
                InventoryItem(
                    code=code,
                    name=str(row.get("name") or code),
                    category=Category.RAEE,
                    quantity_kg=float(row.get("quantity_kg") or 0.0),
                    moisture=float(row.get("moisture") or 0.0),
                    grade_cu=float(row.get("grade_cu") or 0.0),
                    grade_au=float(row.get("grade_au") or 0.0),
                    grade_ag=float(row.get("grade_ag") or 0.0),
                    grade_pt=0.0,
                    grade_pd=float(row.get("grade_pd") or 0.0),
                    grade_source=source,
                )
            )
        except (TypeError, ValueError):
            continue
    return items


def _merge_uploaded(uploaded, current: list[InventoryItem]) -> tuple[list[InventoryItem], int, int]:
    """Carga un xlsx y actualiza cantidades, conservando las leyes ya conocidas."""
    from data.load_inventory import load_inventory, normalize_code  # import perezoso

    parsed = [it for it in load_inventory(uploaded) if it.category == Category.RAEE]
    by_code = {it.code: it for it in current}
    updated, added = 0, 0
    for p in parsed:
        code = normalize_code(p.code)
        if code in by_code:
            by_code[code].quantity_kg = p.quantity_kg
            by_code[code].name = p.name or by_code[code].name
            updated += 1
        else:
            by_code[code] = InventoryItem(
                code=code, name=p.name, category=Category.RAEE,
                quantity_kg=p.quantity_kg, grade_source=GradeSource.MANUAL,
            )
            added += 1
    return list(by_code.values()), updated, added


def render() -> None:
    private = st.session_state.get("private", False)
    items = inventory_items()

    brand("Inventario", "Editá o cargá el stock. Lo que guardes manda en todos los módulos.")
    st.write("")

    graded = [it for it in items if max(it.grade_cu, it.grade_au, it.grade_ag, it.grade_pd) > 0]
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Pilas en stock", f"{len(items)}")
    c2.metric("Con ley", f"{len(graded)}")
    c3.metric("Sin ley (pend. ensayo)", f"{len(items) - len(graded)}")
    c4.metric("Stock total", f"{sum(it.quantity_kg for it in items):,.0f} kg")

    if has_saved_state():
        st.caption("✏️ Estás usando un inventario **guardado/editado** (no el del xlsx original).")
    else:
        st.caption("📄 Estás usando el inventario **real del xlsx** con leyes estimadas.")

    # --- Carga de xlsx ----------------------------------------------------- #
    with st.expander("📤 Cargar inventario desde Excel (.xlsx)"):
        st.caption(
            "Actualiza las cantidades de las pilas existentes (por código) y "
            "agrega las nuevas. Las leyes ya conocidas se conservan."
        )
        uploaded = st.file_uploader("Archivo de inventario", type=["xlsx"], key="inv_upload")
        if uploaded is not None and st.button("Aplicar carga", type="primary"):
            try:
                merged, upd, add = _merge_uploaded(uploaded, items)
                save_state(merged)
                invalidate_caches()
                st.success(f"Inventario cargado: {upd} pilas actualizadas, {add} nuevas.")
                st.rerun()
            except Exception as e:  # noqa: BLE001 - mostrar el error al usuario
                st.error(f"No se pudo leer el archivo: {e}")

    # --- Edición manual ---------------------------------------------------- #
    st.markdown("##### Editar inventario")
    st.caption(
        "Cambiá cantidades y leyes; agregá filas con el **+** abajo. "
        "Cu en fracción (0.21 = 21%); Au/Ag/Pd en g/t. Tocá **Guardar** para aplicar."
    )
    df = _items_to_df(items, private)
    edited = st.data_editor(
        df,
        width="stretch",
        height=380,
        num_rows="dynamic",
        hide_index=True,
        key="inv_edit",
        disabled=["Pila"],
        column_config={
            "Pila": st.column_config.TextColumn("Pila", help="Etiqueta (número de la pila)."),
            "name": None,  # nombre nunca visible (privacidad): solo código
            "quantity_kg": st.column_config.NumberColumn("quantity_kg", min_value=0.0, format="%.1f"),
            "moisture": st.column_config.NumberColumn("moisture", min_value=0.0, max_value=1.0, format="%.3f"),
            "grade_source": st.column_config.SelectboxColumn(
                "grade_source", options=[s.value for s in GradeSource]
            ),
        },
    )

    b1, b2, _ = st.columns([1, 1, 2])
    if b1.button("💾 Guardar cambios", type="primary", width="stretch"):
        new_items = _df_to_items(edited.drop(columns=["Pila"], errors="ignore"))
        if not new_items:
            st.warning("No hay pilas válidas para guardar.")
        else:
            save_state(new_items)
            invalidate_caches()
            st.success(f"Inventario guardado ({len(new_items)} pilas). Aplicado a todos los módulos.")
            st.rerun()
    if b2.button("↺ Restablecer al original", width="stretch"):
        reset_state()
        invalidate_caches()
        st.info("Inventario restablecido al xlsx original.")
        st.rerun()
