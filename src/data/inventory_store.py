"""Estado persistente del inventario (para edición/carga en tiempo real).

La app arranca del inventario real (``inventory.xlsx``) con leyes estimadas. Si
el usuario edita o carga inventario desde la UI, el estado se guarda en
``data/inventory_state.json`` y pasa a ser la **fuente de verdad** para todos
los módulos (simulador, optimizador, panel). Así una carga de inventario se
refleja en tiempo real y sobrevive reinicios del servidor.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Iterable, Optional

from domain.models import Category, GradeSource, InventoryItem

STATE_PATH = Path(__file__).resolve().parents[2] / "data" / "inventory_state.json"


def _item_to_dict(it: InventoryItem) -> dict:
    return {
        "code": it.code,
        "name": it.name,
        "category": it.category.value,
        "quantity_kg": it.quantity_kg,
        "moisture": it.moisture,
        "grade_cu": it.grade_cu,
        "grade_au": it.grade_au,
        "grade_ag": it.grade_ag,
        "grade_pt": it.grade_pt,
        "grade_pd": it.grade_pd,
        "grade_source": it.grade_source.value,
        "grade_confidence": it.grade_confidence,
    }


def _item_from_dict(d: dict) -> InventoryItem:
    try:
        source = GradeSource(d.get("grade_source", "manual"))
    except ValueError:
        source = GradeSource.MANUAL
    try:
        category = Category(d.get("category", "RAEE"))
    except ValueError:
        category = Category.RAEE
    return InventoryItem(
        code=str(d["code"]),
        name=str(d.get("name", d["code"])),
        category=category,
        quantity_kg=float(d.get("quantity_kg", 0.0) or 0.0),
        moisture=float(d.get("moisture", 0.01) or 0.0),
        grade_cu=float(d.get("grade_cu", 0.0) or 0.0),
        grade_au=float(d.get("grade_au", 0.0) or 0.0),
        grade_ag=float(d.get("grade_ag", 0.0) or 0.0),
        grade_pt=float(d.get("grade_pt", 0.0) or 0.0),
        grade_pd=float(d.get("grade_pd", 0.0) or 0.0),
        grade_source=source,
        grade_confidence=d.get("grade_confidence"),
    )


def has_saved_state(path: Path = STATE_PATH) -> bool:
    return path.exists()


def load_saved_state(path: Path = STATE_PATH) -> Optional[list[InventoryItem]]:
    """Inventario guardado por el usuario, o ``None`` si no hay."""
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return [_item_from_dict(d) for d in data.get("items", [])]
    except (json.JSONDecodeError, KeyError, ValueError, OSError):
        return None


def save_state(items: Iterable[InventoryItem], path: Path = STATE_PATH) -> None:
    """Persiste el inventario como fuente de verdad."""
    payload = {"items": [_item_to_dict(it) for it in items]}
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def reset_state(path: Path = STATE_PATH) -> None:
    """Vuelve al inventario base (borra el estado guardado)."""
    if path.exists():
        path.unlink()
