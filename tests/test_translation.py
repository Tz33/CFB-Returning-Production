"""Tests for transfer translation math."""
import pandas as pd
import pytest

from analysis.estimate_transfer_translation import translation_table
from db.translation import TRANSLATION, translate


def test_translate_applies_coefficient():
    expected = 500 * TRANSLATION["offense"][("G", "P")]
    assert translate(500, "G", "P", "offense") == pytest.approx(expected)


def test_translation_table_includes_zero_dest():
    movers = pd.DataFrame({
        "origin_tier": ["G", "G"],
        "dest_tier": ["P", "P"],
        "origin_production": [500, 500],
        "dest_production": [400, 0],  # one bust — must count, not drop
    })
    table = translation_table(movers)
    row = table.loc[("G", "P")]
    assert row["n"] == 2
    assert row["aggregate_ratio"] == pytest.approx(400 / 1000)
    assert row["zero_dest_share"] == pytest.approx(0.5)


def test_coefficient_plausibility():
    for side in ("offense", "defense"):
        assert TRANSLATION[side][("G", "P")] < 1.0  # stepping up costs production
        assert TRANSLATION[side][("P", "G")] > 1.0  # stepping down boosts it
