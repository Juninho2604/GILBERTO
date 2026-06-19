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
from pathlib import Path

import streamlit as st

from data.bootstrap import default_inventory
from domain.models import InventoryItem, default_prices, default_terms
from domain.valuation import BlendComponent, value_blend
from optimize.optimizer import optimize_partition

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
    """Inventario RAEE real con leyes estimadas (con stock). Las 40 pilas."""
    return default_inventory(with_stock_only=True)


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


@st.cache_resource(show_spinner=False)
def default_optimum() -> dict:
    """Óptimo del inventario actual con precios/términos por defecto (panel).

    Compara las estrategias simples (separado / una sola mezcla) contra la mejor
    partición, **sobre el mismo universo de pilas con ley** (sin peso muerto de
    pilas sin ensayo). Cacheado: corre una vez por sesión.
    """
    prices, terms = default_prices(), default_terms()
    items = optimizable_items()

    separate = sum(
        value_blend([BlendComponent(it, it.quantity_kg)], prices, terms).net_value_usd
        for it in items
    )
    single = value_blend(
        [BlendComponent(it, it.quantity_kg) for it in items], prices, terms
    ).net_value_usd

    best, best_k = None, 1
    for k in (1, 2, 3):
        res = optimize_partition(items, prices, terms, num_lots=k, time_limit_s=20.0)
        if res.lots and (best is None or res.net_value_usd > best.net_value_usd):
            best, best_k = res, k

    best_usd = best.net_value_usd if best else single
    baseline = max(separate, single)  # mejor estrategia "humana" simple
    return {
        "separate_usd": separate,
        "single_usd": single,
        "best_usd": best_usd,
        "best_num_lots": best_k,
        "baseline_usd": baseline,
        "gain_vs_single_usd": best_usd - single,
        "gain_vs_single_pct": 100.0 * (best_usd - single) / single if single else 0.0,
        "gain_vs_best_simple_usd": best_usd - baseline,
        "gain_vs_best_simple_pct": 100.0 * (best_usd - baseline) / baseline if baseline else 0.0,
        "graded_stock_kg": sum(it.quantity_kg for it in items),
        "n_graded": len(items),
        "total_stock_kg": sum(it.quantity_kg for it in inventory_items()),
        "n_items": len(inventory_items()),
    }
