"""Fotos de la precisión del modelo en el tiempo (``data/model_snapshots.json``).

El argumento de renovación del servicio es medible: "con tus últimas
liquidaciones, el modelo pasó de X% a Y% de error". Cada vez que se recalcula
el estudio del histórico se guarda una foto (fecha, lotes, error de dinero,
error por metal, cobertura). El Panel muestra la evolución entre fotos.
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

SNAPSHOT_PATH = Path(__file__).resolve().parents[2] / "data" / "model_snapshots.json"

_METALS = ("CU", "AU", "AG", "PD")


def _snapshot_from_analysis(analysis: dict) -> dict:
    """Extrae del estudio los indicadores que definen 'qué tan bueno' es el modelo."""
    errs = {p["metal"]: p["median_abs_err_pct"] for p in analysis.get("precision", [])}
    cov = analysis.get("coverage", {})
    return {
        "n_lots": analysis.get("n_lots", 0),
        "n_resolvable": analysis.get("n_resolvable", 0),
        "money_fidelity_pct": round(float(analysis.get("money_fidelity_pct", 0.0)), 2),
        "err_pct": {m: round(float(errs.get(m, 0.0)), 2) for m in _METALS},
        "coverage_covered": cov.get("covered", 0),
        "coverage_stocked": cov.get("stocked_items", 0),
    }


def load_snapshots(path: Path = SNAPSHOT_PATH) -> list[dict]:
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        snaps = data.get("snapshots", [])
        return snaps if isinstance(snaps, list) else []
    except (json.JSONDecodeError, OSError):
        return []


def record_snapshot(analysis: dict, path: Path = SNAPSHOT_PATH) -> bool:
    """Registra una foto del estudio. Devuelve True si se agregó.

    No duplica: si los indicadores son idénticos a la última foto (mismo nº de
    lotes y misma precisión), recalcular sin datos nuevos no agrega ruido.
    """
    snap = _snapshot_from_analysis(analysis)
    snaps = load_snapshots(path)
    if snaps:
        last = {k: v for k, v in snaps[-1].items() if k != "timestamp"}
        if last == snap:
            return False
    snap_full = {"timestamp": datetime.now().isoformat(timespec="seconds"), **snap}
    snaps.append(snap_full)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps({"snapshots": snaps}, ensure_ascii=False, indent=2),
                   encoding="utf-8")
    tmp.replace(path)
    return True
