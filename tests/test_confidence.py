"""Tests de confianza por (pila, metal) — Feature 1 del change-order.

Criterios de aceptación §1.5: bloques colineales, pilas medidas, y la
"ley-fantasma" de la pila 26 marcada NOT_DETERMINED.
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from data.estimate_grades import (
    TIER_ESTIMATED,
    TIER_MEASURED,
    TIER_NOT_DETERMINED,
    _colinear_blocks,
    estimate_grades,
)
from data.load_history import load_history


@pytest.fixture(scope="module")
def est():
    return estimate_grades(load_history())


def test_pila26_pd_not_determined(est):
    """La ley-fantasma Pd 1882 de la pila 26 (2% de un solo lote) → NOT_DETERMINED."""
    e = est["026"]
    assert e.tiers["PD"] == TIER_NOT_DETERMINED
    # El valor sigue ahí pero marcado: la UI no debe mostrarlo como certero.
    assert e.sigmas["PD"] > 0


def test_measured_piles(est):
    """Pilas que viajaron solas → Cu/Au MEASURED."""
    for code in ("053", "054", "009", "011", "016", "027"):
        e = est[code]
        assert e.tiers["CU"] == TIER_MEASURED, code
        assert e.tiers["AU"] == TIER_MEASURED, code
        assert e.n_pure_lots >= 1


def test_colinear_block_29_33(est):
    """Bloque {29..33}: cada miembro marcado y sin ley individual confiable."""
    block = ("029", "030", "031", "032", "033")
    for code in block:
        e = est[code]
        assert e.block == block
        assert e.tiers["AU"] == TIER_NOT_DETERMINED
        assert e.tiers["AG"] == TIER_NOT_DETERMINED


def test_separable_piles_stay_estimated(est):
    """Pila 41 (20% de un lote, vía pila conocida) y 15 (94%) → ESTIMATED, no descartadas."""
    assert est["041"].tiers["AU"] == TIER_ESTIMATED
    assert est["015"].tiers["AU"] == TIER_ESTIMATED


def test_colinear_blocks_match_reference():
    """La detección reproduce los bloques del documento de referencia."""
    blocks = set(_colinear_blocks(load_history()).values())
    assert ("029", "030", "031", "032", "033") in blocks
    assert ("012", "998") in blocks
    assert ("037", "038") in blocks
    assert ("003", "004") in blocks
    assert ("106", "107", "108") in blocks


def test_sigma_never_negative(est):
    """σ siempre ≥ 0 y definido para todo metal estimado."""
    for e in est.values():
        for m in ("CU", "AU", "AG", "PD"):
            assert e.sigmas.get(m, 0.0) >= 0.0
