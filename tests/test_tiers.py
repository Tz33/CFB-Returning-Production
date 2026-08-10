"""Tests for conference tier classification."""
from db.tiers import conference_tier


def test_power_conferences():
    assert conference_tier("SEC", 2024) == "P"
    assert conference_tier("Big Ten", 2015) == "P"


def test_group_of_five():
    assert conference_tier("Sun Belt", 2024) == "G"
    assert conference_tier("Mountain West", 2018) == "G"


def test_pac12_era_split():
    assert conference_tier("Pac-12", 2023) == "P"
    assert conference_tier("Pac-12", 2024) == "G"
    assert conference_tier("Pac-10", 2015) == "P"


def test_notre_dame_independent():
    assert conference_tier("FBS Independents", 2024, school="Notre Dame") == "P"
    assert conference_tier("FBS Independents", 2024, school="UMass") == "G"


def test_none_conference_is_group():
    assert conference_tier(None, 2024) == "G"
