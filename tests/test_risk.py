"""Tests de riesgo de umbral — Feature 2 del change-order (§2.7)."""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from domain.models import Category, InventoryItem, default_terms
from domain.risk import DEFAULT_Z_MIN, blend_threshold_risk, grade_safe, norm_cdf
from domain.valuation import BlendComponent


def _pile(code, ag, ag_sigma, qty=1000.0):
    it = InventoryItem(code=code, name=code, category=Category.RAEE, moisture=0.0,
                       quantity_kg=qty, grade_ag=ag)
    it.grade_sigma = {"AG": ag_sigma}
    return it


def test_ag_on_the_edge_is_risky():
    """Ag 112 ±70 (umbral 100): P_cobro ≈ 57% y z < z_min → lote frágil."""
    terms = default_terms()
    comps = [BlendComponent(_pile("X", 112, 70), 1000.0)]
    risk = blend_threshold_risk(comps, terms)["AG"]
    assert risk.grade == pytest.approx(112)
    assert risk.sigma == pytest.approx(70)
    assert risk.p_cobro == pytest.approx(0.568, abs=0.02)   # ~57%
    assert not risk.safe(DEFAULT_Z_MIN)                     # z ≈ 0.17 < 1.5


def test_diluting_with_rich_pile_stabilizes():
    """Mezclar la ruidosa con una rica baja σ y sube z → cobro casi seguro."""
    terms = default_terms()
    comps = [
        BlendComponent(_pile("RUID", 120, 70), 1000.0),
        BlendComponent(_pile("RICA", 600, 50), 1000.0),
    ]
    risk = blend_threshold_risk(comps, terms)["AG"]
    # 50/50: grade 360, sigma = sqrt(.5²·70² + .5²·50²) ≈ 43 (ejemplo del doc).
    assert risk.grade == pytest.approx(360)
    assert risk.sigma == pytest.approx(43.0, abs=1.0)
    assert risk.z > 5
    assert risk.safe(DEFAULT_Z_MIN)
    assert risk.p_cobro > 0.99


def test_grade_safe_never_below_threshold():
    assert grade_safe(112, 70, 100, k=1.0) == 100      # 112−70 < 100 → clamp
    assert grade_safe(360, 43, 100, k=1.0) == pytest.approx(317)


def test_norm_cdf_basic():
    assert norm_cdf(0.0) == pytest.approx(0.5)
    assert norm_cdf(1.5) == pytest.approx(0.933, abs=0.005)
