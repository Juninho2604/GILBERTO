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


@dataclass
class ContainerLoad:
    """Un contenedor cargado: qué lote(s) lleva y cuántos kg de cada uno."""

    index: int
    container_kg: float
    segments: list[tuple[int, float, bool]]  # (n_lote, kg, es_anticipo)

    @property
    def total_kg(self) -> float:
        return sum(kg for _, kg, _ in self.segments)

    @property
    def fill_pct(self) -> float:
        return 100.0 * self.total_kg / self.container_kg if self.container_kg else 0.0


def pack_lots(
    lot_weights: list[float], container_kg: float, final_lot_kg: float
) -> list[ContainerLoad]:
    """Empaqueta los lotes finales en contenedores de ``container_kg``.

    Cada contenedor lleva 1 lote final (hasta ``final_lot_kg``) y, si sobra
    espacio, **anticipo**: material del siguiente lote que viaja para usar el
    contenedor y queda esperando en Miami para el próximo armado.
    """
    containers: list[ContainerLoad] = []
    cur: list[tuple[int, float, bool]] = []
    cur_kg = 0.0
    lot_filled = 0.0  # cuánto del "lote principal" de este contenedor ya se cargó

    def flush():
        nonlocal cur, cur_kg, lot_filled
        if cur:
            containers.append(ContainerLoad(len(containers) + 1, container_kg, cur))
        cur, cur_kg, lot_filled = [], 0.0, 0.0

    for li, w in enumerate(lot_weights, 1):
        remaining = w
        while remaining > 1e-6:
            space = container_kg - cur_kg
            if space <= 1e-6:
                flush()
                space = container_kg
            take = min(space, remaining)
            # Es anticipo si el contenedor ya completó un lote final.
            es_anticipo = lot_filled >= final_lot_kg - 1e-6
            cur.append((li, take, es_anticipo))
            cur_kg += take
            lot_filled += take
            remaining -= take
    flush()
    return containers

