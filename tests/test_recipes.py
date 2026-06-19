"""Tests del parser de recetas (sección 6)."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from data.recipes import parse_recipe


def test_pure_single_item():
    r = parse_recipe("11")
    assert r.resolvable
    assert r.fractions == {"011": 1.0}


def test_all_percentages_sum_100():
    r = parse_recipe("1*(28%) + 2*(58%) + 14*(14%)")
    assert r.resolvable
    assert r.fractions["001"] == 0.28
    assert r.fractions["002"] == 0.58
    assert r.fractions["014"] == 0.14
    assert abs(sum(r.fractions.values()) - 1.0) < 1e-9


def test_single_base_takes_remainder():
    # 022 = 8%, 026 = 2%, 015 = resto (90%).
    r = parse_recipe("15 + 22*(8%) + 26*(2%)")
    assert r.resolvable
    assert r.fractions["022"] == 0.08
    assert r.fractions["026"] == 0.02
    assert abs(r.fractions["015"] - 0.90) < 1e-9


def test_bare_percent_without_parens():
    # "6 + 8*33%": 008 = 33%, 006 = 67%.
    r = parse_recipe("6 + 8*33%")
    assert r.resolvable
    assert abs(r.fractions["008"] - 0.33) < 1e-9
    assert abs(r.fractions["006"] - 0.67) < 1e-9


def test_two_bases_ambiguous_equal_split():
    r = parse_recipe("37 + 38")
    assert not r.resolvable
    assert r.assumed_equal_split
    assert r.fractions["037"] == 0.5
    assert r.fractions["038"] == 0.5


def test_free_text_not_parseable():
    r = parse_recipe("Credicar / Credit Card Reader Boards")
    assert not r.resolvable
    assert r.fractions == {}
