"""Tests for tenure-to-season coach-change mapping."""
from etl.load_coach_changes import seasons_with_new_coach

TENURES = [
    {"firstName": "Old", "lastName": "Coach", "startYear": 2010, "endYear": 2021, "isInterim": False},
    {"firstName": "Interim", "lastName": "Guy", "startYear": 2022, "endYear": 2022, "isInterim": True},
    {"firstName": "New", "lastName": "Coach", "startYear": 2023, "endYear": None, "isInterim": False},
]


def test_continuity_season():
    flags = seasons_with_new_coach(TENURES, 2020, 2020)[2020]
    assert flags["new_head_coach"] is False
    assert flags["coach_name"] == "Old Coach"
    assert flags["tenure_start_year"] == 2010


def test_interim_season_flagged():
    flags = seasons_with_new_coach(TENURES, 2022, 2022)[2022]
    assert flags["new_head_coach"] is True
    assert flags["is_interim"] is True


def test_new_coach_season():
    flags = seasons_with_new_coach(TENURES, 2023, 2023)[2023]
    assert flags["new_head_coach"] is True
    assert flags["is_interim"] is False
    assert flags["coach_name"] == "New Coach"


def test_open_ended_tenure_covers_later_seasons():
    flags = seasons_with_new_coach(TENURES, 2025, 2025)[2025]
    assert flags["new_head_coach"] is False
    assert flags["coach_name"] == "New Coach"


def test_nested_coach_object():
    tenures = [{"coach": {"id": 68, "firstName": "Troy", "lastName": "Calhoun"},
                "startYear": 2007, "endYear": None, "isInterim": False}]
    flags = seasons_with_new_coach(tenures, 2020, 2020)[2020]
    assert flags["coach_name"] == "Troy Calhoun"


def test_null_start_year_uses_effective_start():
    tenures = [{"firstName": "Eff", "lastName": "Start", "startYear": None,
                "effectiveStart": "2019-01-15", "endYear": None, "isInterim": False}]
    flags = seasons_with_new_coach(tenures, 2019, 2019)[2019]
    assert flags["new_head_coach"] is True
    assert flags["tenure_start_year"] == 2019
