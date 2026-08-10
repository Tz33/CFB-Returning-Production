"""Tests for betting-line provider selection and cover margin."""
from analysis.validate_market_spreads import cover_margin
from etl.load_game_lines import pick_line


def test_pick_line_prefers_consensus():
    lines = [
        {"provider": "numberfire", "spread": -3.0},
        {"provider": "consensus", "spread": -3.5},
    ]
    assert pick_line(lines)["provider"] == "consensus"


def test_pick_line_falls_back_when_preferred_has_no_spread():
    lines = [
        {"provider": "consensus", "spread": None},
        {"provider": "DraftKings", "spread": -7.0},
    ]
    assert pick_line(lines)["provider"] == "DraftKings"


def test_pick_line_unknown_provider_still_used():
    lines = [{"provider": "SomeNewBook", "spread": -2.5}]
    assert pick_line(lines)["provider"] == "SomeNewBook"


def test_pick_line_none_when_no_spreads():
    assert pick_line([{"provider": "consensus", "spread": None}]) is None
    assert pick_line([]) is None


def test_cover_margin():
    # home favored by 7, wins by 10 -> covers by 3
    assert cover_margin(home_score=30, away_score=20, spread=-7.0) == 3.0
    # home favored by 7, wins by 7 -> push (0)
    assert cover_margin(home_score=27, away_score=20, spread=-7.0) == 0.0
    # home underdog by 3, loses by 1 -> covers by 2
    assert cover_margin(home_score=20, away_score=21, spread=3.0) == 2.0
