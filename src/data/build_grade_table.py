"""Genera la tabla de leyes estimadas como entregable de datos (sección 6).

Carga inventario + histórico, estima las leyes y vuelca un CSV
(``data/estimated_grades.csv``) con ley por metal, origen y confianza, para
sembrar el simulador y para que Gilberto valide contra los ensayos reales.

Uso:  python -m data.build_grade_table
"""

from __future__ import annotations

import csv
from pathlib import Path

from domain.models import METALS

from .estimate_grades import estimate_grades
from .load_history import load_history
from .load_inventory import load_raee_inventory

OUTPUT_CSV = Path(__file__).resolve().parents[2] / "data" / "estimated_grades.csv"


def build(output: Path = OUTPUT_CSV) -> Path:
    inv = load_raee_inventory(with_stock_only=False)
    names = {it.code: it.name for it in inv}
    stock = {it.code: it.quantity_kg for it in inv}
    est = estimate_grades(load_history(), names=names)

    rows = []
    for code in sorted(est):
        e = est[code]
        rows.append(
            {
                "code": code,
                "name": e.name,
                "stock_kg": round(stock.get(code, 0.0), 2),
                "grade_cu": round(e.grades.get("CU", 0.0), 4),
                "grade_au": round(e.grades.get("AU", 0.0), 1),
                "grade_ag": round(e.grades.get("AG", 0.0), 1),
                "grade_pt": round(e.grades.get("PT", 0.0), 1),
                "grade_pd": round(e.grades.get("PD", 0.0), 1),
                "confidence": e.confidence.value,
                "n_pure_lots": e.n_pure_lots,
                "n_recipes": e.n_recipes,
                "note": e.note,
            }
        )

    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    return output


if __name__ == "__main__":  # pragma: no cover
    path = build()
    print(f"Tabla de leyes escrita en: {path}")
