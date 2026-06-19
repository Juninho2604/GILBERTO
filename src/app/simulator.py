"""Simulador de mezclas RAEE — Fase 1 (MVP), UI en Streamlit.

El usuario edita inventario (incluidas las leyes), precios y términos del
contrato, elige cuánto de cada pila entra en la mezcla y ve **en vivo**: la
ley resultante por metal, el monto por metal, los cargos, el valor neto USD y
el USD/kg. Replica la planilla histórica, pero viva.

Ejecutar:  streamlit run src/app/simulator.py
"""

from __future__ import annotations

import sys
from pathlib import Path

# Permite ``import domain`` al correr con `streamlit run src/app/simulator.py`.
SRC = Path(__file__).resolve().parents[1]
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

import pandas as pd
import streamlit as st

from data.bootstrap import default_inventory
from domain.models import (
    METALS,
    Category,
    ContractTerms,
    GradeSource,
    InventoryItem,
    MetalPrices,
    RecoveryRule,
    default_prices,
    default_terms,
)
from domain.valuation import BlendComponent, value_blend
from optimize.optimizer import optimize_blend, optimize_partition

st.set_page_config(page_title="Optimizador de Mezclas RAEE", layout="wide")

USD = "${:,.2f}".format


# --------------------------------------------------------------------------- #
# Estado inicial (editable por el usuario)
# --------------------------------------------------------------------------- #
def _inventory_to_df(items: list[InventoryItem]) -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "code": it.code,
                "name": it.name,
                "quantity_kg": it.quantity_kg,
                "moisture": it.moisture,
                "grade_cu": it.grade_cu,
                "grade_au": it.grade_au,
                "grade_ag": it.grade_ag,
                "grade_pt": it.grade_pt,
                "grade_pd": it.grade_pd,
                "grade_source": it.grade_source.value,
                "blend_kg": 0.0,
            }
            for it in items
        ]
    )


def _init_state() -> None:
    if "inventory_df" not in st.session_state:
        st.session_state.inventory_df = _inventory_to_df(default_inventory())
    if "prices" not in st.session_state:
        st.session_state.prices = default_prices()
    if "terms" not in st.session_state:
        st.session_state.terms = default_terms()


def _df_to_items(df: pd.DataFrame) -> list[InventoryItem]:
    """Convierte el inventario editado de la UI en ítems de dominio."""
    items = []
    for _, row in df.iterrows():
        try:
            items.append(_row_to_item(row))
        except (TypeError, ValueError):
            continue
    return items


def _row_to_item(row) -> InventoryItem:
    try:
        source = GradeSource(row["grade_source"])
    except ValueError:
        source = GradeSource.MANUAL
    return InventoryItem(
        code=str(row["code"]),
        name=str(row["name"]),
        category=Category.RAEE,
        quantity_kg=float(row["quantity_kg"]),
        moisture=float(row["moisture"]),
        grade_cu=float(row["grade_cu"]),
        grade_au=float(row["grade_au"]),
        grade_ag=float(row["grade_ag"]),
        grade_pt=float(row["grade_pt"]),
        grade_pd=float(row["grade_pd"]),
        grade_source=source,
    )


# --------------------------------------------------------------------------- #
# Sidebar: precios y términos del contrato
# --------------------------------------------------------------------------- #
def _sidebar_prices_and_terms() -> tuple[MetalPrices, ContractTerms]:
    p: MetalPrices = st.session_state.prices
    t: ContractTerms = st.session_state.terms

    st.sidebar.header("Precios del día")
    st.sidebar.caption("Cu en USD/t · preciosos en USD/onza troy (sección 10).")
    price_cu = st.sidebar.number_input("price_cu (USD/t)", value=float(p.price_cu), step=10.0, format="%.2f")
    price_au = st.sidebar.number_input("price_au (USD/oz)", value=float(p.price_au), step=10.0, format="%.2f")
    price_ag = st.sidebar.number_input("price_ag (USD/oz)", value=float(p.price_ag), step=0.5, format="%.2f")
    price_pt = st.sidebar.number_input("price_pt (USD/oz)", value=float(p.price_pt), step=10.0, format="%.2f")
    price_pd = st.sidebar.number_input("price_pd (USD/oz)", value=float(p.price_pd), step=10.0, format="%.2f")
    prices = MetalPrices(price_cu, price_au, price_ag, price_pt, price_pd)

    st.sidebar.header("Términos del contrato")
    with st.sidebar.expander("Refining charges (RC)"):
        rc_cu = st.number_input("rc_cu (USD/t)", value=float(t.rc_cu), step=10.0, format="%.2f")
        rc_au = st.number_input("rc_au (USD/oz)", value=float(t.rc_au), step=0.5, format="%.2f")
        rc_ag = st.number_input("rc_ag (USD/oz)", value=float(t.rc_ag), step=0.1, format="%.2f")
        rc_pt = st.number_input("rc_pt (USD/oz)", value=float(t.rc_pt), step=0.5, format="%.2f")
        rc_pd = st.number_input("rc_pd (USD/oz)", value=float(t.rc_pd), step=0.5, format="%.2f")
    with st.sidebar.expander("Cargos de procesamiento"):
        tc_rate = st.number_input("treatment (USD/Dt)", value=float(t.tc_rate), step=10.0, format="%.2f")
        shred_rate = st.number_input("shredding (USD/t húmeda)", value=float(t.shred_rate), step=10.0, format="%.2f")
        min_lot_charge = st.number_input("min lot charge", value=float(t.min_lot_charge), step=10.0, format="%.2f")
        moisture_penalty = st.number_input("moisture penalty", value=float(t.moisture_penalty), step=10.0, format="%.2f")
    with st.sidebar.expander("Deducciones y topes (RR — CONFIRMAR)"):
        cu_ded = st.number_input("Cu: deducción (puntos %)", value=float(t.cu_deduction), step=0.01, format="%.3f")
        au_ded = st.number_input("Au: deducción (g/t)", value=float(t.au_rule.deduction), step=1.0, format="%.1f")
        au_cap = st.number_input("Au: tope RR", value=float(t.au_rule.cap or 0.96), step=0.01, format="%.2f")
        ag_ded = st.number_input("Ag: deducción (g/t)", value=float(t.ag_rule.deduction), step=1.0, format="%.1f")
        ag_cap = st.number_input("Ag: tope RR", value=float(t.ag_rule.cap or 0.95), step=0.01, format="%.2f")
        pd_ded = st.number_input("Pd: deducción (g/t)", value=float(t.pd_rule.deduction), step=1.0, format="%.1f")
        pt_paid = st.checkbox("Pt se paga", value=t.pt_rule.paid)
        pt_ded = st.number_input("Pt: deducción (g/t)", value=float(t.pt_rule.deduction), step=1.0, format="%.1f")

    terms = ContractTerms(
        rc_cu=rc_cu, rc_au=rc_au, rc_ag=rc_ag, rc_pt=rc_pt, rc_pd=rc_pd,
        cu_deduction=cu_ded,
        au_rule=RecoveryRule(deduction=au_ded, cap=au_cap),
        ag_rule=RecoveryRule(deduction=ag_ded, cap=ag_cap, floor_zero=True),
        pd_rule=RecoveryRule(deduction=pd_ded, cap=None, floor_zero=True),
        pt_rule=RecoveryRule(deduction=pt_ded, paid=pt_paid, floor_zero=True),
        tc_rate=tc_rate, shred_rate=shred_rate,
        min_lot_charge=min_lot_charge, moisture_penalty=moisture_penalty,
    )

    st.session_state.prices = prices
    st.session_state.terms = terms
    return prices, terms


# --------------------------------------------------------------------------- #
# App
# --------------------------------------------------------------------------- #
def _inventory_editor() -> pd.DataFrame:
    st.subheader("Inventario (editable, incluidas las leyes)")
    st.caption(
        "Cargado del inventario real con **leyes estimadas** desde el histórico "
        "(sección 6). grade_cu en fracción (0.21 = 21%); Au/Ag/Pt/Pd en g/t. "
        "**blend_kg** = cuánto de esa pila entra en la mezcla manual."
    )
    edited = st.data_editor(
        st.session_state.inventory_df,
        num_rows="dynamic",
        width="stretch",
        height=380,
        key="inv_editor",
        column_config={
            "grade_source": st.column_config.SelectboxColumn(
                "grade_source", options=[s.value for s in GradeSource]
            ),
            "blend_kg": st.column_config.NumberColumn("blend_kg", min_value=0.0),
        },
    )
    st.session_state.inventory_df = edited
    return edited


def _render_lot_result(result, *, key: str) -> None:
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Valor neto (USD)", USD(result.net_value_usd))
    c2.metric("USD / kg", f"{result.result_per_kg:,.2f}")
    c3.metric("WMT (kg)", f"{result.wmt:,.1f}")
    c4.metric("DMT (kg)", f"{result.dmt:,.1f}")

    metal_rows = []
    for m in METALS:
        r = result.metals[m]
        unit = "fracción" if m == "CU" else "g/t"
        content_unit = "kg" if m == "CU" else "g"
        metal_rows.append(
            {
                "metal": m,
                f"ley ({unit})": round(r.grade, 4),
                f"contenido ({content_unit})": round(r.content, 2),
                "RR": round(r.rr, 4),
                f"recuperado ({content_unit})": round(r.recovered, 2),
                "monto USD": round(r.amount_usd, 2),
            }
        )
    st.dataframe(pd.DataFrame(metal_rows), width="stretch", hide_index=True)
    charges = pd.DataFrame(
        [
            {"concepto": "Metal total", "USD": round(result.metal_total, 2)},
            {"concepto": "− Treatment", "USD": -round(result.treatment_charge, 2)},
            {"concepto": "− Shredding", "USD": -round(result.shredding_charge, 2)},
            {"concepto": "− Min lot charge", "USD": -round(result.min_lot_charge, 2)},
            {"concepto": "− Moisture penalty", "USD": -round(result.moisture_penalty, 2)},
            {"concepto": "= Valor neto", "USD": round(result.net_value_usd, 2)},
        ]
    )
    st.dataframe(charges, width="stretch", hide_index=True)


def _tab_simulator(edited: pd.DataFrame, prices: MetalPrices, terms: ContractTerms) -> None:
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
                f"{item.name}: blend_kg ({blend_kg:,.0f}) supera el stock "
                f"({item.quantity_kg:,.0f} kg)."
            )
        components.append(BlendComponent(item, blend_kg))

    for w in warnings:
        st.warning("⚠️ " + w)

    if not components:
        st.info(
            "Cargá una cantidad en **blend_kg** para al menos una pila y mirá el "
            "resultado en vivo. (O usá la pestaña **Optimizador** para que el "
            "sistema arme las mezclas óptimas solo.)"
        )
        return

    st.subheader("Resultado de la mezcla")
    _render_lot_result(value_blend(components, prices, terms), key="sim")


def _tab_optimizer(edited: pd.DataFrame, prices: MetalPrices, terms: ContractTerms) -> None:
    st.subheader("Optimizador de mezclas (Fase 2)")
    st.caption(
        "Reparte todo el inventario en lotes para que la refinería pague lo "
        "máximo. Clave: **no diluir** las pilas ricas en oro con relleno pobre "
        "(la deducción de 7 g/t de Au se aplica sobre toda la masa)."
    )
    c1, c2, c3 = st.columns(3)
    num_lots = c1.slider("Cantidad de lotes", 1, 4, 2)
    min_lot_kg = c2.number_input("Tamaño mínimo por lote (kg)", value=0.0, step=100.0)
    run = c3.button("▶ Optimizar", type="primary", width="stretch")

    if not run:
        st.info("Ajustá los parámetros y tocá **Optimizar**.")
        return

    items = [it for it in _df_to_items(edited) if it.quantity_kg > 0]
    with st.spinner("Resolviendo MILP…"):
        res = optimize_partition(
            items, prices, terms, num_lots=num_lots, min_lot_kg=min_lot_kg
        )
    if not res.lots:
        st.warning(f"Sin solución (status={res.status}).")
        return

    st.success(
        f"Status: {res.status} · **Valor total: {USD(res.net_value_usd)}** "
        f"en {len(res.lots)} lote(s)."
    )
    for i, lot in enumerate(res.lots, 1):
        v = lot.valuation
        with st.expander(
            f"Lote {i} — {lot.total_weight_kg:,.0f} kg · "
            f"{USD(v.net_value_usd)} ({v.result_per_kg:.2f} USD/kg) · "
            f"Au {v.metals['AU'].grade:.0f} g/t",
            expanded=(i == 1),
        ):
            comp_df = pd.DataFrame(
                [
                    {"code": p.item.code, "name": p.item.name, "kg": round(p.weight_kg, 1)}
                    for p in lot.components
                ]
            )
            st.dataframe(comp_df, width="stretch", hide_index=True)
            _render_lot_result(v, key=f"opt{i}")
    if res.leftover:
        st.caption(
            "Material sin asignar (no conviene enviarlo): "
            + ", ".join(f"{c}={kg:,.0f}kg" for c, kg in res.leftover.items())
        )


def main() -> None:
    _init_state()
    st.title("Optimizador de Mezclas RAEE")
    st.caption(
        "Servicios Megabytes, C.A. · **Simulador** (Fase 1) para iterar mezclas "
        "a mano y **Optimizador** (Fase 2) para que el sistema las arme solo."
    )

    prices, terms = _sidebar_prices_and_terms()
    edited = _inventory_editor()

    tab_sim, tab_opt = st.tabs(["🧪 Simulador", "🎯 Optimizador"])
    with tab_sim:
        _tab_simulator(edited, prices, terms)
    with tab_opt:
        _tab_optimizer(edited, prices, terms)


if __name__ == "__main__":
    main()
