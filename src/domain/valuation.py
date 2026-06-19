"""Valorización de un lote / mezcla — LA FÓRMULA (sección 3 del brief).

Replicada exactamente de la planilla histórica de la refinería. Módulo puro,
sin dependencias de UI, validado contra el Apéndice A.

Flujo por metal:  contenido → recuperado (RR) → monto USD.
Flujo del lote:   Σ montos − cargos = valor neto.

Convenciones:
- ``grade_cu`` en fracción (0.21 = 21%), precio en USD/tonelada.
- metales preciosos en g/t, precio en USD/onza troy.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from .models import (
    METALS,
    PRECIOUS_METALS,
    TROY_OUNCE_G,
    ContractTerms,
    InventoryItem,
    MetalPrices,
    RecoveryRule,
)


@dataclass
class MetalResult:
    """Desglose de un metal dentro del lote valorizado."""

    metal: str
    grade: float          # ley usada (fracción para CU, g/t para preciosos)
    content: float        # contenido (kg para CU, g para preciosos)
    rr: float             # recovery rate aplicado
    recovered: float      # metal recuperado (kg para CU, g para preciosos)
    unit_price: float     # precio neto de RC (USD/t para CU, USD/oz preciosos)
    amount_usd: float     # monto en USD


@dataclass
class LotValuation:
    """Resultado completo de valorizar un lote (sección 3.5)."""

    wmt: float
    dmt: float
    metals: dict[str, MetalResult]
    metal_total: float
    treatment_charge: float
    shredding_charge: float
    min_lot_charge: float
    moisture_penalty: float
    charges_total: float
    net_value_usd: float
    result_per_kg: float


@dataclass
class BlendComponent:
    """Cuánto de una pila entra en la mezcla (sección 4.4)."""

    item: InventoryItem
    weight_kg: float  # WMT aportado por esta pila (≤ item.quantity_kg)

    @property
    def dry_weight_kg(self) -> float:
        return self.weight_kg * (1.0 - self.item.moisture)


# --------------------------------------------------------------------------- #
# Recovery Rate
# --------------------------------------------------------------------------- #
def recovery_rate_cu(grade_cu: float, terms: ContractTerms) -> float:
    """RR del cobre: ``(g - deduction) / g`` (sección 3.2 / tabla 3.3).

    Nota: la planilla original incluía ramas ``IF(grade>=20)`` / ``IF(grade>=23)``
    que nunca se activan (comparan la ley en fracción contra 20/23). Se
    implementa el comportamiento real: deducir los puntos porcentuales.
    """
    if grade_cu <= 0:
        return 0.0
    return (grade_cu - terms.cu_deduction) / grade_cu


def recovery_rate_precious(grade: float, rule: RecoveryRule) -> float:
    """RR de un metal precioso según su :class:`RecoveryRule` (tabla 3.3)."""
    if not rule.paid or grade <= 0:
        return 0.0
    rr = (grade - rule.deduction) / grade
    if rule.floor_zero:
        rr = max(0.0, rr)
    if rule.cap is not None:
        rr = min(rule.cap, rr)
    return rr


# --------------------------------------------------------------------------- #
# Valorización de un lote a partir de pesos + leyes
# --------------------------------------------------------------------------- #
def _metal_result_cu(
    grade_cu: float, dmt: float, prices: MetalPrices, terms: ContractTerms
) -> MetalResult:
    content_kg = grade_cu * dmt
    rr = recovery_rate_cu(grade_cu, terms)
    recovered_kg = content_kg * rr
    unit_price = prices.price_cu - terms.rc_cu
    amount_usd = recovered_kg * unit_price / 1000.0  # kg → tonelada
    return MetalResult("CU", grade_cu, content_kg, rr, recovered_kg, unit_price, amount_usd)


def _metal_result_precious(
    metal: str, grade: float, dmt: float, prices: MetalPrices, terms: ContractTerms
) -> MetalResult:
    rule = terms.rule(metal)
    content_g = (dmt / 1000.0) * grade
    rr = recovery_rate_precious(grade, rule)
    recovered_g = content_g * rr
    unit_price = prices.price(metal) - terms.rc(metal)
    amount_usd = recovered_g * unit_price / TROY_OUNCE_G  # gramos → onza troy
    return MetalResult(metal, grade, content_g, rr, recovered_g, unit_price, amount_usd)


def value_lot(
    wmt: float,
    moisture: float,
    grades: dict[str, float],
    prices: MetalPrices,
    terms: ContractTerms,
) -> LotValuation:
    """Valoriza un lote dado su WMT, humedad y leyes (secciones 3.1–3.5).

    ``grades`` mapea símbolo de metal → ley (``"CU"`` en fracción, preciosos
    en g/t). Los metales ausentes se tratan como ley 0.
    """
    dmt = wmt * (1.0 - moisture)

    results: dict[str, MetalResult] = {}
    results["CU"] = _metal_result_cu(grades.get("CU", 0.0), dmt, prices, terms)
    for metal in PRECIOUS_METALS:
        results[metal] = _metal_result_precious(
            metal, grades.get(metal, 0.0), dmt, prices, terms
        )

    metal_total = sum(r.amount_usd for r in results.values())

    treatment_charge = (dmt / 1000.0) * terms.tc_rate
    shredding_charge = (wmt / 1000.0) * terms.shred_rate
    min_lot_charge = terms.min_lot_charge
    moisture_penalty = terms.moisture_penalty
    charges_total = (
        treatment_charge + shredding_charge + min_lot_charge + moisture_penalty
    )

    net_value_usd = metal_total - charges_total
    result_per_kg = net_value_usd / wmt if wmt else 0.0

    return LotValuation(
        wmt=wmt,
        dmt=dmt,
        metals=results,
        metal_total=metal_total,
        treatment_charge=treatment_charge,
        shredding_charge=shredding_charge,
        min_lot_charge=min_lot_charge,
        moisture_penalty=moisture_penalty,
        charges_total=charges_total,
        net_value_usd=net_value_usd,
        result_per_kg=result_per_kg,
    )


# --------------------------------------------------------------------------- #
# Valorización de una MEZCLA (sección 3.6)
# --------------------------------------------------------------------------- #
def blend_grades(components: Iterable[BlendComponent]) -> dict[str, float]:
    """Leyes del lote combinado: promedio ponderado por peso seco (sección 3.6).

    ``grade_blend(m) = Σ (grade_i(m) × dry_weight_i) / Σ dry_weight_i``.
    """
    components = list(components)
    dmt_blend = sum(c.dry_weight_kg for c in components)
    grades: dict[str, float] = {m: 0.0 for m in METALS}
    if dmt_blend <= 0:
        return grades
    for metal in METALS:
        weighted = sum(c.item.grade(metal) * c.dry_weight_kg for c in components)
        grades[metal] = weighted / dmt_blend
    return grades


def value_blend(
    components: Iterable[BlendComponent],
    prices: MetalPrices,
    terms: ContractTerms,
) -> LotValuation:
    """Valoriza una mezcla de pilas (sección 3.6).

    Combina los pesos, computa las leyes ponderadas por peso seco y aplica la
    fórmula del lote. La humedad efectiva del lote sale del peso seco agregado.
    """
    components = list(components)
    wmt_blend = sum(c.weight_kg for c in components)
    dmt_blend = sum(c.dry_weight_kg for c in components)
    effective_moisture = 1.0 - (dmt_blend / wmt_blend) if wmt_blend else 0.0
    grades = blend_grades(components)
    return value_lot(wmt_blend, effective_moisture, grades, prices, terms)
