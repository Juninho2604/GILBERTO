"""Inventario por defecto para la app: real + leyes estimadas, con fallback.

Intenta cargar el inventario RAEE real (``data/inventory.xlsx``) y sembrar las
leyes estimadas desde el histórico (sección 6). Si los archivos no están,
cae en el inventario de demostración de ``seed.py``.
"""

from __future__ import annotations

from applog import get_logger
from domain.models import InventoryItem

from .seed import seed_inventory

_LOG = get_logger("aurix.data")

# True si la última carga cayó al inventario de EJEMPLO (faltan los xlsx reales).
# La UI lo consulta para mostrar un aviso fuerte: optimizar datos falsos creyendo
# que son reales es el peor fallo silencioso posible.
LAST_LOAD_FALLBACK = False


def default_inventory(with_stock_only: bool = True) -> list[InventoryItem]:
    """Inventario RAEE con leyes estimadas cargadas (o fallback de demo)."""
    global LAST_LOAD_FALLBACK
    try:
        from .estimate_grades import apply_estimates_to_inventory, estimate_grades
        from .load_history import load_history
        from .load_inventory import load_raee_inventory
        from .unmeasured_grades import apply_conservative_grades

        inv = load_raee_inventory(with_stock_only=with_stock_only)
        names = {it.code: it.name for it in inv}
        est = estimate_grades(load_history(), names=names)
        inv = apply_estimates_to_inventory(inv, est)
        # Las pilas sin receta (no estimables) reciben un piso conservador de
        # mercado para que no queden invisibles al optimizador.
        inv = apply_conservative_grades(inv)
        # Dejamos primero las pilas con ley estimada por regresión.
        inv.sort(key=lambda it: (it.code not in est, -it.quantity_kg))
        LAST_LOAD_FALLBACK = False
        return inv
    except Exception:  # pragma: no cover - fallback si faltan datos/libs
        _LOG.exception(
            "No se pudo cargar el inventario real (¿falta data/inventory.xlsx o "
            "refining_history.xlsx?). Usando datos de EJEMPLO."
        )
        LAST_LOAD_FALLBACK = True
        return seed_inventory()
