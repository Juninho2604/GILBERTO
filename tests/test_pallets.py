"""Tests del plan de carga por pallets (app.viz3d.build_pallets)."""

from app.viz3d import (
    PALLET_KG,
    RICH_FILL,
    RICH_LOW,
    RICH_VERY,
    LotViz,
    build_pallets,
    pallet_figure,
)


def _lots():
    return [
        LotViz(index=1, weight_kg=4200, util_pct=95, au_grade=120, codes=["001"]),
        LotViz(index=2, weight_kg=8000, util_pct=88, au_grade=60, codes=["046"]),
        LotViz(index=3, weight_kg=10800, util_pct=72, au_grade=15,
               codes=["022"], below_threshold=True),
    ]


def test_numbering_is_contiguous_and_in_richness_order():
    pallets = build_pallets(_lots())
    assert [p.number for p in pallets] == list(range(1, len(pallets) + 1))
    # El primer pallet pertenece al lote más rico en oro.
    assert pallets[0].lot_index == 1
    assert pallets[0].tier == RICH_VERY


def test_tiers_follow_relative_gold_grade():
    pallets = build_pallets(_lots())
    tier_by_lot = {p.lot_index: p.tier for p in pallets}
    assert tier_by_lot[1] == RICH_VERY   # 120/120 = 1.0
    assert tier_by_lot[2] == RICH_LOW    # 60/120 = 0.5
    assert tier_by_lot[3] == RICH_FILL   # 15/120 = 0.125


def test_total_weight_is_preserved():
    lots = _lots()
    pallets = build_pallets(lots)
    assert abs(sum(p.weight_kg for p in pallets)
               - sum(l.weight_kg for l in lots)) < 1e-6


def test_pallet_count_is_about_one_tonne_each():
    lots = _lots()
    pallets = build_pallets(lots)
    for p in pallets:
        assert p.weight_kg <= PALLET_KG + 1e-6


def test_below_threshold_propagates_to_pallets():
    pallets = build_pallets(_lots())
    below = [p for p in pallets if p.below_threshold]
    assert below and all(p.lot_index == 3 for p in below)


def test_single_lot_is_very_rich():
    pallets = build_pallets(
        [LotViz(index=1, weight_kg=2000, util_pct=90, au_grade=40, codes=["x"])]
    )
    assert all(p.tier == RICH_VERY for p in pallets)


def test_figure_builds_without_error():
    fig = pallet_figure(build_pallets(_lots()), 23000)
    assert len(fig.data) > 0
