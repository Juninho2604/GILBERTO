"""Tests de la fórmula de valorización (sección 3 del brief).

El caso central es el **Apéndice A**: el primer lote histórico verificado.
La implementación debe reproducir esos números antes de avanzar.
"""

import math

import pytest

from domain.models import (
    Category,
    ContractTerms,
    InventoryItem,
    MetalPrices,
    RecoveryRule,
    default_prices,
    default_terms,
)
from domain.valuation import (
    BlendComponent,
    recovery_rate_cu,
    recovery_rate_precious,
    value_blend,
    value_lot,
)


# --------------------------------------------------------------------------- #
# Apéndice A — test de aceptación
# --------------------------------------------------------------------------- #
APPENDIX_A_PRICES = MetalPrices(
    price_cu=11_803.79, price_au=4_500.0, price_ag=64.34, price_pt=0.0, price_pd=1_569.0
)
APPENDIX_A_TERMS = ContractTerms(
    rc_cu=300.0, rc_au=5.0, rc_ag=0.5, rc_pt=0.0, rc_pd=14.0,
    tc_rate=600.0, shred_rate=100.0,
)
APPENDIX_A_GRADES = {"CU": 0.2113, "AU": 84.4, "AG": 646.0, "PT": 0.0, "PD": 4.3}


@pytest.fixture
def appendix_a():
    return value_lot(
        wmt=5184.0,
        moisture=0.009,
        grades=APPENDIX_A_GRADES,
        prices=APPENDIX_A_PRICES,
        terms=APPENDIX_A_TERMS,
    )


def test_appendix_a_dmt(appendix_a):
    assert appendix_a.dmt == pytest.approx(5137.344, abs=1e-3)


@pytest.mark.parametrize(
    "metal, content, rr, recovered, amount",
    [
        ("CU", 1085.52, 0.8580, 931.40, 10_714.64),
        ("AU", 433.59, 0.9171, 397.63, 57_464.60),
        ("AG", 3318.72, 0.8452, 2804.99, 5_757.25),
        ("PD", 22.09, 0.0000, 0.0, 0.0),
    ],
)
def test_appendix_a_per_metal(appendix_a, metal, content, rr, recovered, amount):
    r = appendix_a.metals[metal]
    assert r.content == pytest.approx(content, abs=0.01)
    assert r.rr == pytest.approx(rr, abs=1e-4)
    assert r.recovered == pytest.approx(recovered, abs=0.01)
    assert r.amount_usd == pytest.approx(amount, abs=0.05)


def test_appendix_a_totals(appendix_a):
    assert appendix_a.metal_total == pytest.approx(73_936.49, abs=0.1)
    assert appendix_a.treatment_charge == pytest.approx(3_082.41, abs=0.01)
    assert appendix_a.shredding_charge == pytest.approx(518.40, abs=0.01)
    assert appendix_a.charges_total == pytest.approx(3_600.81, abs=0.02)
    assert appendix_a.net_value_usd == pytest.approx(70_335.68, abs=0.1)
    assert appendix_a.result_per_kg == pytest.approx(13.57, abs=0.01)


# --------------------------------------------------------------------------- #
# Recovery Rate unitarios (tabla 3.3)
# --------------------------------------------------------------------------- #
def test_rr_cu_deducts_three_points():
    terms = default_terms()
    assert recovery_rate_cu(0.2113, terms) == pytest.approx((0.2113 - 0.03) / 0.2113)
    assert recovery_rate_cu(0.0, terms) == 0.0


def test_rr_au_capped_at_96():
    rule = RecoveryRule(deduction=7.0, cap=0.96)
    # ley muy alta → toca el tope
    assert recovery_rate_precious(10_000.0, rule) == pytest.approx(0.96)
    assert recovery_rate_precious(84.4, rule) == pytest.approx((84.4 - 7) / 84.4)


def test_rr_ag_floor_zero():
    rule = RecoveryRule(deduction=100.0, cap=0.95, floor_zero=True)
    # bajo el umbral de 100 g/t → no paga
    assert recovery_rate_precious(80.0, rule) == 0.0


def test_rr_pd_below_deduction_is_zero():
    # El caso del Apéndice A: 4.3 g/t < 18 g/t → 0.
    rule = RecoveryRule(deduction=18.0, floor_zero=True)
    assert recovery_rate_precious(4.3, rule) == 0.0


def test_pt_not_paid_by_default():
    terms = default_terms()
    assert recovery_rate_precious(500.0, terms.pt_rule) == 0.0


# --------------------------------------------------------------------------- #
# Mezcla (sección 3.6) — la intuición económica de "rescatar" metal sub-umbral
# --------------------------------------------------------------------------- #
def test_blend_weighted_grades_and_rescue():
    """Una pila pobre sola no paga su Pd, pero mezclada con una rica sí."""
    prices = default_prices()
    terms = default_terms()

    rich = InventoryItem(
        code="RICH", name="Rica", category=Category.RAEE,
        quantity_kg=1000, moisture=0.0,
        grade_cu=0.25, grade_au=120.0, grade_ag=800.0, grade_pd=60.0,
    )
    poor = InventoryItem(
        code="POOR", name="Pobre", category=Category.RAEE,
        quantity_kg=1000, moisture=0.0,
        grade_cu=0.05, grade_au=2.0, grade_ag=20.0, grade_pd=4.0,
    )

    # Pd de la pila pobre sola: 4 g/t < 18 → no paga.
    poor_alone = value_blend([BlendComponent(poor, 1000)], prices, terms)
    assert poor_alone.metals["PD"].amount_usd == 0.0

    # Mezclada 50/50 (mismo peso seco): Pd ponderado = 32 g/t > 18 → paga.
    blend = value_blend(
        [BlendComponent(rich, 1000), BlendComponent(poor, 1000)], prices, terms
    )
    assert blend.metals["PD"].grade == pytest.approx(32.0)
    assert blend.metals["PD"].amount_usd > 0.0
    # Ley de Cu ponderada por peso seco (sin humedad) = promedio simple.
    assert blend.metals["CU"].grade == pytest.approx(0.15)


def test_blend_moisture_weighting():
    """El peso seco pondera las leyes y define la humedad efectiva del lote."""
    prices = default_prices()
    terms = default_terms()
    wet = InventoryItem("W", "Húmeda", quantity_kg=1000, moisture=0.20, grade_au=100.0)
    dry = InventoryItem("D", "Seca", quantity_kg=1000, moisture=0.00, grade_au=50.0)
    blend = value_blend(
        [BlendComponent(wet, 1000), BlendComponent(dry, 1000)], prices, terms
    )
    # dry_weight: wet=800, dry=1000 → DMT=1800, WMT=2000.
    assert blend.wmt == pytest.approx(2000.0)
    assert blend.dmt == pytest.approx(1800.0)
    # Au ponderado = (100*800 + 50*1000)/1800.
    assert blend.metals["AU"].grade == pytest.approx((100 * 800 + 50 * 1000) / 1800)


def test_empty_blend_is_zero():
    prices = default_prices()
    terms = default_terms()
    result = value_blend([], prices, terms)
    assert result.net_value_usd == 0.0
    assert result.result_per_kg == 0.0
    assert not math.isnan(result.result_per_kg)
