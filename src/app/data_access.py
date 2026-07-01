"""Acceso a datos para la UI, con caché de las operaciones caras.

- El **estudio del histórico** se lee del artefacto JSON precomputado
  (``data/history_analysis.json``); si falta, se calcula en vivo (lento).
- El **inventario** real con leyes estimadas se cachea.
- El **óptimo del inventario actual** con precios/términos por defecto se cachea
  para el panel; la pestaña Optimizador recalcula en vivo con los valores que el
  usuario edite.
"""

from __future__ import annotations

import json
from math import ceil
from pathlib import Path

import streamlit as st

from data.bootstrap import default_inventory
from data.inventory_store import load_saved_state
from domain.models import InventoryItem, default_prices, default_terms

_HISTORY_JSON = Path(__file__).resolve().parents[2] / "data" / "history_analysis.json"


@st.cache_data(show_spinner=False)
def history_analysis() -> dict:
    """Estudio del histórico (real vs. óptimo). Del JSON precomputado o en vivo."""
    if _HISTORY_JSON.exists():
        return json.loads(_HISTORY_JSON.read_text(encoding="utf-8"))
    from analysis.historical import analyze_history  # import perezoso

    return analyze_history(default_prices(), default_terms()).to_dict()


@st.cache_data(show_spinner=False)
def inventory_items() -> list[InventoryItem]:
    """Inventario RAEE actual: el guardado por el usuario, o el real del xlsx.

    Si el usuario editó/cargó inventario desde el módulo Inventario, esa versión
    persistida manda (fuente de verdad). Si no, se usa el inventario real con
    leyes estimadas.
    """
    saved = load_saved_state()
    if saved is not None:
        return [it for it in saved if it.quantity_kg > 0]
    return default_inventory(with_stock_only=True)


def invalidate_caches() -> None:
    """Limpia los cachés tras editar/cargar inventario, para refrescar todo."""
    st.cache_data.clear()
    st.cache_resource.clear()


def using_sample_data() -> bool:
    """True si la app está corriendo con inventario de EJEMPLO (no el real).

    Pasa cuando faltan los xlsx en el servidor y no hay estado guardado: el
    fallback evita el crash, pero el usuario TIENE que saber que esos números
    no son su inventario.
    """
    if load_saved_state() is not None:
        return False
    from data import bootstrap

    inventory_items()  # fuerza la carga (cacheada) para que el flag sea fiable
    return bootstrap.LAST_LOAD_FALLBACK


@st.cache_data(show_spinner=False)
def resolvable_lot_ids() -> list[str]:
    """IDs de lotes históricos para la demo: resolubles y de ≥2 pilas (interesantes
    para mostrar la partición y el 3D). Si no hubiera, cae a todos los resolubles."""
    from data.load_history import load_history

    lots = load_history()
    multi = [str(L.customer_lot) for L in lots
             if L.recipe.resolvable and len(L.recipe.fractions) >= 2]
    if multi:
        return multi
    return [str(L.customer_lot) for L in lots if L.recipe.resolvable]


@st.cache_data(show_spinner=False)
def demo_lot(customer_lot: str) -> dict:
    """Reconstruye un lote histórico para la demo: meta + pilas con ley, σ y tier.

    Devuelve lo necesario para (1) mostrar lo que se envió y se cobró, y (2)
    re-optimizar ese mismo material con todo el motor (3D, riesgo, confianza).
    """
    from data.estimate_grades import estimate_grades
    from data.load_history import load_history
    from data.load_inventory import load_raee_inventory
    from domain.models import Category

    lots = load_history()
    lot = next((L for L in lots if str(L.customer_lot) == str(customer_lot)), None)
    if lot is None:
        return {}
    names = {it.code: it.name for it in load_raee_inventory(with_stock_only=False)}
    est = estimate_grades(lots, names=names)

    items: list[InventoryItem] = []
    for code, frac in lot.recipe.fractions.items():
        e = est.get(code)
        if e is None or frac <= 0:
            continue
        it = InventoryItem(
            code=code, name=names.get(code, code), category=Category.RAEE,
            quantity_kg=frac * lot.wmt, moisture=lot.moisture,
            grade_cu=e.grades.get("CU", 0.0), grade_au=e.grades.get("AU", 0.0),
            grade_ag=e.grades.get("AG", 0.0), grade_pt=e.grades.get("PT", 0.0),
            grade_pd=e.grades.get("PD", 0.0), grade_source=e.source,
        )
        it.grade_sigma = dict(e.sigmas)
        it.grade_tier = dict(e.tiers)
        items.append(it)

    return {
        "customer_lot": str(lot.customer_lot),
        "jx_lot": str(lot.jx_lot),
        "recipe_raw": lot.recipe_raw,
        "wmt": lot.wmt,
        "moisture": lot.moisture,
        "measured_grades": dict(lot.grades),
        "items": items,
    }


def _has_grade(it: InventoryItem) -> bool:
    return max(it.grade_cu, it.grade_au, it.grade_ag, it.grade_pt, it.grade_pd) > 0


@st.cache_data(show_spinner=False)
def optimizable_items() -> list[InventoryItem]:
    """Solo las pilas con ley conocida (estimada).

    Las pilas sin ensayo tienen ley 0: el optimizador no puede valorizarlas y
    meterlas en una mezcla solo agregaría peso muerto y cargos. Se excluyen del
    optimizador y de las comparaciones para que el número sea honesto
    (manzanas con manzanas), no inflado por datos faltantes.
    """
    return [it for it in inventory_items() if _has_grade(it)]


_CONTAINER_KG = 23_000.0  # estándar 40' ≈ 23 t


@st.cache_data(show_spinner=False)
def default_optimum() -> dict:
    """El mejor **contenedor de 23 t** del inventario actual (panel).

    Gilberto manda 1 contenedor cada ~3 meses; el panel resume el aprovechamiento
    del próximo envío óptimo (no la partición de todo el stock). Cacheado.
    """
    from optimize.optimizer import optimize_blend

    prices, terms = default_prices(), default_terms()
    items = optimizable_items()
    stock_kg = sum(it.quantity_kg for it in items)
    target = min(_CONTAINER_KG, stock_kg)

    best = optimize_blend(
        items, prices, terms,
        objective="net_usd", min_lot_kg=target, max_lot_kg=_CONTAINER_KG,
    )
    v = best.valuation
    util = v.metal_utilization_pct if v else 0.0
    net_util = v.net_utilization_pct if v else 0.0
    weight = best.total_weight_kg

    n_envios = max(1, ceil(stock_kg / _CONTAINER_KG)) if _CONTAINER_KG else 1
    return {
        "best_util_pct": util,
        "best_net_util_pct": net_util,
        "best_unused_pct": max(0.0, 100.0 - util),
        "best_usd": v.net_value_usd if v else 0.0,
        "container_kg": _CONTAINER_KG,
        "container_weight_kg": weight,
        "container_fill_pct": 100.0 * weight / _CONTAINER_KG if _CONTAINER_KG else 0.0,
        "n_envios": n_envios,
        "graded_stock_kg": stock_kg,
        "n_graded": len(items),
        "total_stock_kg": sum(it.quantity_kg for it in inventory_items()),
        "n_items": len(inventory_items()),
    }
