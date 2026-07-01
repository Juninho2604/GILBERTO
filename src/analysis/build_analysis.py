"""Precomputa el estudio del histórico a un artefacto JSON para la UI.

El estudio corre ~100 MILP chicos (cada lote, varias particiones) y tarda. Para
que la interfaz cargue al instante, lo precomputamos a ``data/history_analysis.json``
y la app lee ese archivo. Regenerar tras cambiar leyes, precios o términos:

    python -m analysis.build_analysis
"""

from __future__ import annotations

import json
from pathlib import Path

from analysis.historical import analyze_history
from domain.models import default_prices, default_terms

OUT = Path(__file__).resolve().parents[2] / "data" / "history_analysis.json"


def build(path: Path = OUT) -> Path:
    analysis = analyze_history(default_prices(), default_terms())
    payload = analysis.to_dict()
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    # Foto de la precisión del modelo: el Panel muestra la evolución entre
    # recalculados ("el modelo pasó de X% a Y% con tus últimas liquidaciones").
    from data.snapshots import record_snapshot

    record_snapshot(payload)
    return path


if __name__ == "__main__":  # pragma: no cover
    p = build()
    data = json.loads(p.read_text(encoding="utf-8"))
    print(f"Escrito {p}")
    print(f"  lotes={data['n_lots']} resolubles={data['n_resolvable']}")
    print(f"  extra={data['extra_usd']:.0f} USD ({data['extra_pct']:+.2f}%)")
    print(f"  sub-umbral perdido={data['sub_threshold_total_usd']:.0f} USD")
