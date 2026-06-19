"""Logística de envío: contenedores y armado del lote final.

El material se exporta en **contenedores** (capacidad configurable) y, al llegar
a Miami, se arma el **lote final** que valoriza la refinería (tope de ~18-19 t).
Este módulo trae las capacidades estándar y el cálculo de cuántos contenedores
hacen falta y su % de llenado.
"""

from __future__ import annotations

from dataclasses import dataclass

# Capacidades de carga típicas (kg) — editables en la UI.
CONTAINERS: dict[str, float | None] = {
    "44' (≈23 t)": 23_000.0,
    "20' Dry Van (≈21,8 t)": 21_800.0,
    "40' Dry Van (≈26,6 t)": 26_600.0,
    "40' High Cube (≈26,6 t)": 26_600.0,
    "Personalizado": None,
}

DEFAULT_CONTAINER = "44' (≈23 t)"
DEFAULT_FINAL_LOT_KG = 18_500.0  # lote final que se arma en Miami (~18-19 t)


@dataclass
class ContainerPlan:
    total_kg: float
    container_kg: float
    n_containers: int
    fill_pct_avg: float        # llenado promedio por contenedor
    fill_pct_last: float       # llenado del último contenedor


def containers_needed(total_kg: float, container_kg: float) -> ContainerPlan:
    """Cuántos contenedores hacen falta para ``total_kg`` y su llenado."""
    if container_kg <= 0 or total_kg <= 0:
        return ContainerPlan(total_kg, container_kg, 0, 0.0, 0.0)
    import math

    n = max(1, math.ceil(total_kg / container_kg))
    last = total_kg - (n - 1) * container_kg
    return ContainerPlan(
        total_kg=total_kg,
        container_kg=container_kg,
        n_containers=n,
        fill_pct_avg=100.0 * total_kg / (n * container_kg),
        fill_pct_last=100.0 * last / container_kg,
    )
