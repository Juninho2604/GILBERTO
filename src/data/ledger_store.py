"""Registro persistente del bono por envío (``data/bono_ledger.json``).

El acumulado de envíos ejecutados es un **registro contractual** (define plata):
no puede vivir solo en la memoria de la sesión, donde un reinicio del servidor
lo borra. Cada entrada guarda timestamp y montos; la escritura es
read-modify-write sobre un JSON con reemplazo atómico (write + rename).
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

LEDGER_PATH = Path(__file__).resolve().parents[2] / "data" / "bono_ledger.json"


def load_ledger(path: Path = LEDGER_PATH) -> list[dict]:
    """Entradas registradas (lista vacía si no hay o el archivo está dañado)."""
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        entries = data.get("entries", [])
        return entries if isinstance(entries, list) else []
    except (json.JSONDecodeError, OSError):
        return []


def _write(entries: list[dict], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(
        json.dumps({"entries": entries}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    tmp.replace(path)  # reemplazo atómico: nunca queda un JSON a medio escribir


def append_entry(
    rescatado_usd: float,
    bono_usd: float,
    mejora_pct: float,
    path: Path = LEDGER_PATH,
) -> list[dict]:
    """Agrega un envío ejecutado y devuelve el ledger actualizado."""
    entries = load_ledger(path)
    entries.append({
        "n": len(entries) + 1,
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "rescatado_usd": round(float(rescatado_usd), 2),
        "bono_usd": round(float(bono_usd), 2),
        "mejora_pct": round(float(mejora_pct), 4),
        "estado": "registrado",  # → "reconciliado" cuando llegue la liquidación
    })
    _write(entries, path)
    return entries


def reconcile_entry(
    n: int, real_usd: float, path: Path = LEDGER_PATH
) -> list[dict]:
    """Marca el envío ``n`` como reconciliado contra la liquidación real.

    Guarda el valor real y la fecha: el bono deja de ser proyección y queda
    atado al dato de la refinería (la regla acordada con el cliente).
    """
    entries = load_ledger(path)
    for e in entries:
        if e.get("n") == n:
            e["estado"] = "reconciliado"
            e["real_usd"] = round(float(real_usd), 2)
            e["reconciled_at"] = datetime.now().isoformat(timespec="seconds")
            break
    _write(entries, path)
    return entries


def clear_ledger(path: Path = LEDGER_PATH) -> None:
    """Vacía el registro (borra el archivo)."""
    if path.exists():
        path.unlink()
