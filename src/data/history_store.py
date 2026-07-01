"""Liquidaciones nuevas cargadas por el usuario (``data/history_extra.json``).

El corazón del "se afina solo": cada liquidación real que devuelve la refinería
se registra acá desde la app — sin tocar el ``.xlsx`` ni redeployar. Al
fusionarse con el histórico en :func:`data.load_history.load_history`, la
liquidación nueva alimenta de inmediato la re-estimación de leyes (regresión,
rápida) y queda disponible para regenerar el estudio completo bajo demanda.
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from applog import get_logger

from .load_history import HistoricLot
from .recipes import parse_recipe

_LOG = get_logger("aurix.history")

EXTRA_PATH = Path(__file__).resolve().parents[2] / "data" / "history_extra.json"

_GRADE_KEYS = ("CU", "AU", "AG", "PT", "PD")


def validate_lot(d: dict, existing_jx: set[str] | None = None) -> list[str]:
    """Problemas de una liquidación a cargar (lista vacía = válida)."""
    errors: list[str] = []
    if not str(d.get("customer_lot", "")).strip():
        errors.append("Falta el número de lote (customer lot).")
    wmt = float(d.get("wmt", 0) or 0)
    if wmt <= 0:
        errors.append("El peso húmedo (WMT) debe ser mayor a 0 kg.")
    moisture = float(d.get("moisture", 0) or 0)
    if not (0.0 <= moisture < 0.9):
        errors.append("La humedad debe estar entre 0 y 0.9 (fracción).")
    grades = d.get("grades", {}) or {}
    if any(float(grades.get(m, 0) or 0) < 0 for m in _GRADE_KEYS):
        errors.append("Las leyes no pueden ser negativas.")
    if not any(float(grades.get(m, 0) or 0) > 0 for m in _GRADE_KEYS):
        errors.append("Cargá al menos una ley mayor a 0 (Cu/Au/Ag/Pd).")
    jx = str(d.get("jx_lot", "")).strip()
    if existing_jx and jx and jx in existing_jx:
        errors.append(f"El lote JX '{jx}' ya existe en el histórico (duplicado).")
    return errors


def load_extra_raw(path: Path = EXTRA_PATH) -> list[dict]:
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        lots = data.get("lots", [])
        return lots if isinstance(lots, list) else []
    except (json.JSONDecodeError, OSError):
        return []


def append_lot(d: dict, path: Path = EXTRA_PATH) -> dict:
    """Registra una liquidación nueva (ya validada) y la devuelve normalizada."""
    entry = {
        "customer_lot": str(d["customer_lot"]).strip(),
        "jx_lot": str(d.get("jx_lot", "")).strip(),
        "wmt": float(d["wmt"]),
        "moisture": float(d.get("moisture", 0.0) or 0.0),
        "grades": {m: float((d.get("grades") or {}).get(m, 0) or 0) for m in _GRADE_KEYS},
        "recipe_raw": str(d.get("recipe_raw", "")).strip(),
        "loaded_at": datetime.now().isoformat(timespec="seconds"),
    }
    lots = load_extra_raw(path)
    lots.append(entry)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps({"lots": lots}, ensure_ascii=False, indent=2),
                   encoding="utf-8")
    tmp.replace(path)  # escritura atómica
    _LOG.info("Liquidación cargada: lote %s (JX %s), %.0f kg, receta '%s'.",
              entry["customer_lot"], entry["jx_lot"] or "s/d", entry["wmt"],
              entry["recipe_raw"] or "s/d")
    return entry


def extra_lots(path: Path = EXTRA_PATH) -> list[HistoricLot]:
    """Liquidaciones cargadas por el usuario, como :class:`HistoricLot`."""
    out: list[HistoricLot] = []
    for d in load_extra_raw(path):
        wmt = float(d.get("wmt", 0) or 0)
        moisture = float(d.get("moisture", 0) or 0)
        recipe_raw = str(d.get("recipe_raw", ""))
        out.append(HistoricLot(
            customer_lot=d.get("customer_lot"),
            jx_lot=d.get("jx_lot"),
            wmt=wmt,
            moisture=moisture,
            dmt=wmt * (1.0 - moisture),
            grades={m: float((d.get("grades") or {}).get(m, 0) or 0)
                    for m in _GRADE_KEYS},
            recipe_raw=recipe_raw,
            recipe=parse_recipe(recipe_raw),
        ))
    return out


def count_extra(path: Path = EXTRA_PATH) -> int:
    return len(load_extra_raw(path))
