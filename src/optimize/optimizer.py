"""Optimizador de mezclas RAEE — Fase 2 del brief.

**Objetivo (definido por el usuario):** encontrar las mezclas óptimas del
inventario para que la refinería pague lo máximo posible, aprovechando cada
material — rescatar el metal de las pilas pobres mezclándolas con ricas para
superar los umbrales de deducción, sin agregar tanto peso muerto que los cargos
y las deducciones por tonelada se coman la ganancia.

### Por qué es un MILP "lindo"

Como las deducciones de la refinería son **por tonelada**, el metal recuperado
de una mezcla es **lineal por tramos** en los pesos de las pilas. Para un metal
precioso, en el tramo productivo (mezcla sobre el umbral y bajo el tope):

    recovered_m = Σ_i dry_i · (grade_i,m − deduction_m) / 1000      (gramos)

lineal en los pesos ``dry_i``. Las dos no linealidades se modelan exactas:

- **Tope** (RR ≤ cap): ``r_m = min(cap·content, content − d·toneladas)`` →
  ``r_m ≤`` ambas (se maximiza ⇒ toma el mínimo).
- **Piso / umbral** (``MAX(0, …)``): binaria ``y_m`` por metal y por lote. Si
  la mezcla no llega al umbral, ``r_m = 0``; si lo supera, toma el valor lineal.

### Dos modos

- :func:`optimize_blend` — **un solo lote**: qué pilas y cuánto enviar ahora.
- :func:`optimize_partition` — **varios lotes**: cómo repartir TODO el
  inventario en ``num_lots`` envíos para maximizar el valor total. Captura la
  clave: conviene **no diluir** las pilas ricas en oro con relleno pobre,
  porque la deducción de 7 g/t de Au se aplicaría sobre toda esa masa.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional, Sequence

import pulp

from domain.models import (
    PRECIOUS_METALS,
    TROY_OUNCE_G,
    ContractTerms,
    InventoryItem,
    MetalPrices,
)
from domain.valuation import BlendComponent, LotValuation, value_blend


@dataclass
class BlendPlan:
    """Una pila incluida en una mezcla, con su peso (WMT)."""

    item: InventoryItem
    weight_kg: float


@dataclass
class OptimizeResult:
    """Resultado de optimizar un solo lote."""

    status: str
    weights: dict[str, float]
    components: list[BlendPlan] = field(default_factory=list)
    valuation: Optional[LotValuation] = None
    objective: str = "net_usd"

    @property
    def net_value_usd(self) -> float:
        return self.valuation.net_value_usd if self.valuation else 0.0

    @property
    def total_weight_kg(self) -> float:
        return sum(self.weights.values())


@dataclass
class LotResult:
    """Un lote dentro de una partición."""

    components: list[BlendPlan]
    valuation: LotValuation

    @property
    def total_weight_kg(self) -> float:
        return sum(p.weight_kg for p in self.components)


@dataclass
class PartitionResult:
    """Resultado de repartir el inventario en varios lotes."""

    status: str
    lots: list[LotResult] = field(default_factory=list)
    leftover: dict[str, float] = field(default_factory=dict)  # code → kg sin asignar

    @property
    def net_value_usd(self) -> float:
        return sum(l.valuation.net_value_usd for l in self.lots)


# --------------------------------------------------------------------------- #
# Análisis de apoyo (sin solver)
# --------------------------------------------------------------------------- #
def marginal_values(
    items: Sequence[InventoryItem], prices: MetalPrices, terms: ContractTerms
) -> dict[str, float]:
    """USD/kg de cada pila **enviada sola**. Intuición de qué paga por sí misma."""
    out: dict[str, float] = {}
    for it in items:
        v = value_blend([BlendComponent(it, max(it.quantity_kg, 1.0))], prices, terms)
        out[it.code] = v.result_per_kg
    return out


# --------------------------------------------------------------------------- #
# Núcleo: expresión del valor neto de UN lote sobre variables de peso
# --------------------------------------------------------------------------- #
def _add_lot_net_expr(
    prob: pulp.LpProblem,
    cand: Sequence[InventoryItem],
    x: dict[str, pulp.LpVariable],
    prices: MetalPrices,
    terms: ContractTerms,
    tag: str,
    big_m: float,
):
    """Agrega a ``prob`` las variables/restricciones de un lote y devuelve
    ``(net_expr, wmt_expr, dmt_expr)``."""
    dry = {it.code: x[it.code] * (1.0 - it.moisture) for it in cand}
    wmt = pulp.lpSum(x.values())
    dmt = pulp.lpSum(dry.values())

    amounts = []

    # Cobre: lineal (umbral cu_deduction, sin tope).
    cu_unit = prices.price_cu - terms.rc_cu
    cu_recovered = pulp.lpSum(
        dry[it.code] * (it.grade_cu - terms.cu_deduction) for it in cand
    )
    amounts.append(cu_recovered * cu_unit / 1000.0)

    # Preciosos.
    for metal in PRECIOUS_METALS:
        rule = terms.rule(metal)
        unit = prices.price(metal) - terms.rc(metal)
        if not rule.paid or unit <= 0:
            continue
        content_g = pulp.lpSum(dry[it.code] * it.grade(metal) for it in cand) / 1000.0
        uncapped = content_g - rule.deduction * (dmt / 1000.0)  # Σ dry(g−d)/1000

        r = pulp.LpVariable(f"r_{metal}_{tag}", lowBound=0)
        if rule.floor_zero:
            y = pulp.LpVariable(f"y_{metal}_{tag}", cat="Binary")
            prob += r <= uncapped + big_m * (1 - y)
            prob += r <= big_m * y
            if rule.cap is not None:
                prob += r <= rule.cap * content_g + big_m * (1 - y)
        else:
            prob += r <= uncapped
            if rule.cap is not None:
                prob += r <= rule.cap * content_g
        amounts.append(r * unit / TROY_OUNCE_G)

    treatment = dmt / 1000.0 * terms.tc_rate
    shredding = wmt / 1000.0 * terms.shred_rate
    charges = treatment + shredding + terms.min_lot_charge + terms.moisture_penalty
    net = pulp.lpSum(amounts) - charges
    return net, wmt, dmt


def _exact_valuation(
    cand_by_code: dict[str, InventoryItem],
    weights: dict[str, float],
    prices: MetalPrices,
    terms: ContractTerms,
) -> tuple[list[BlendPlan], Optional[LotValuation]]:
    comps = [
        BlendPlan(cand_by_code[c], w) for c, w in weights.items() if w > 1e-3
    ]
    if not comps:
        return [], None
    val = value_blend(
        [BlendComponent(p.item, p.weight_kg) for p in comps], prices, terms
    )
    return sorted(comps, key=lambda p: -p.weight_kg), val


# --------------------------------------------------------------------------- #
# Modo 1 — un solo lote
# --------------------------------------------------------------------------- #
def optimize_blend(
    items: Sequence[InventoryItem],
    prices: MetalPrices,
    terms: ContractTerms,
    *,
    objective: str = "net_usd",
    min_lot_kg: float = 0.0,
    max_lot_kg: Optional[float] = None,
    required_codes: Sequence[str] = (),
    solver: Optional[pulp.LpSolver] = None,
) -> OptimizeResult:
    """Mejor mezcla de un único lote (qué pilas y cuánto enviar ahora).

    ``objective="net_usd"`` maximiza el valor neto; ``"per_kg"`` maximiza la
    calidad (USD/kg) fijando el tamaño del lote a ``min_lot_kg``.
    """
    cand = [it for it in items if it.quantity_kg > 0]
    if not cand:
        return OptimizeResult(status="empty", weights={})

    big_m = 10.0 * sum(it.quantity_kg for it in cand) * _max_grade(cand) + 1e6
    prob = pulp.LpProblem("blend", pulp.LpMaximize)
    x = {
        it.code: pulp.LpVariable(f"x_{it.code}", lowBound=0, upBound=it.quantity_kg)
        for it in cand
    }
    net, wmt, _ = _add_lot_net_expr(prob, cand, x, prices, terms, "L0", big_m)

    if objective == "per_kg" and min_lot_kg > 0:
        prob += wmt == min_lot_kg
    prob += net

    if objective != "per_kg" and min_lot_kg > 0:
        prob += wmt >= min_lot_kg
    if max_lot_kg is not None:
        prob += wmt <= max_lot_kg
    for code in required_codes:
        if code in x:
            prob += x[code] >= 1e-6

    prob.solve(solver or pulp.PULP_CBC_CMD(msg=False))

    cand_by_code = {it.code: it for it in cand}
    weights = {c: float(x[c].value() or 0.0) for c in x}
    comps, val = _exact_valuation(cand_by_code, weights, prices, terms)
    return OptimizeResult(
        status=pulp.LpStatus[prob.status],
        weights={c: w for c, w in weights.items() if w > 1e-3},
        components=comps,
        valuation=val,
        objective=objective,
    )


# --------------------------------------------------------------------------- #
# Modo 2 — partición en varios lotes
# --------------------------------------------------------------------------- #
def optimize_partition(
    items: Sequence[InventoryItem],
    prices: MetalPrices,
    terms: ContractTerms,
    *,
    num_lots: int = 2,
    min_lot_kg: float = 0.0,
    max_lot_kg: Optional[float] = None,
    solver: Optional[pulp.LpSolver] = None,
    time_limit_s: Optional[float] = 30.0,
) -> PartitionResult:
    """Reparte el inventario en ``num_lots`` lotes para maximizar el valor total.

    Responde a "¿cuáles son las mezclas óptimas?": decide cuánto de cada pila va
    a cada lote (puede dejar material sin asignar si no conviene enviarlo).
    ``min_lot_kg`` impone un tamaño mínimo por lote activo; ``max_lot_kg`` impone
    el tope físico de un lote (p. ej. el lote final de ~18-19 t que se arma en
    Miami, o la capacidad del contenedor).
    """
    cand = [it for it in items if it.quantity_kg > 0]
    if not cand:
        return PartitionResult(status="empty")

    total_stock = sum(it.quantity_kg for it in cand)
    big_m = 10.0 * total_stock * _max_grade(cand) + 1e6
    prob = pulp.LpProblem("partition", pulp.LpMaximize)

    # x[i,k] = kg de pila i en lote k.
    x = {
        (it.code, k): pulp.LpVariable(f"x_{it.code}_{k}", lowBound=0, upBound=it.quantity_kg)
        for it in cand
        for k in range(num_lots)
    }
    # No usar más que el stock de cada pila.
    for it in cand:
        prob += pulp.lpSum(x[(it.code, k)] for k in range(num_lots)) <= it.quantity_kg

    # Tope superior de un lote: el menor entre el stock total y el max físico.
    cap = min(total_stock, max_lot_kg) if max_lot_kg else total_stock

    nets = []
    for k in range(num_lots):
        xk = {it.code: x[(it.code, k)] for it in cand}
        net_k, wmt_k, _ = _add_lot_net_expr(prob, cand, xk, prices, terms, f"L{k}", big_m)
        nets.append(net_k)
        if min_lot_kg > 0:
            u = pulp.LpVariable(f"use_{k}", cat="Binary")
            prob += wmt_k >= min_lot_kg * u
            prob += wmt_k <= cap * u
        elif max_lot_kg:
            prob += wmt_k <= max_lot_kg  # tope físico del lote / contenedor
        # Rompe simetría: ordena lotes por peso decreciente.
        if k > 0:
            prev = {it.code: x[(it.code, k - 1)] for it in cand}
            prob += pulp.lpSum(prev.values()) >= pulp.lpSum(xk.values())

    prob += pulp.lpSum(nets)

    cmd = solver
    if cmd is None:
        kwargs = {"msg": False}
        if time_limit_s:
            kwargs["timeLimit"] = time_limit_s
        cmd = pulp.PULP_CBC_CMD(**kwargs)
    prob.solve(cmd)

    cand_by_code = {it.code: it for it in cand}
    lots: list[LotResult] = []
    assigned: dict[str, float] = {it.code: 0.0 for it in cand}
    for k in range(num_lots):
        weights = {it.code: float(x[(it.code, k)].value() or 0.0) for it in cand}
        for c, w in weights.items():
            assigned[c] += w
        comps, val = _exact_valuation(cand_by_code, weights, prices, terms)
        if val is not None:
            lots.append(LotResult(components=comps, valuation=val))

    leftover = {
        c: cand_by_code[c].quantity_kg - assigned[c]
        for c in assigned
        if cand_by_code[c].quantity_kg - assigned[c] > 1e-3
    }
    return PartitionResult(
        status=pulp.LpStatus[prob.status],
        lots=sorted(lots, key=lambda l: -l.total_weight_kg),
        leftover=leftover,
    )


def _max_grade(items: Sequence[InventoryItem]) -> float:
    """Cota para Big-M: mayor ley (g/t) entre las pilas (Au/Ag suelen mandar)."""
    g = 1.0
    for it in items:
        g = max(g, it.grade_au, it.grade_ag, it.grade_pt, it.grade_pd)
    return g
