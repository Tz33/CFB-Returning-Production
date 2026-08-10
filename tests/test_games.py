"""Tests for /games row shaping."""
from etl.load_games import game_row

TEAM_IDS = {"LSU": 1, "Alabama": 2}


def test_fbs_vs_fcs_kept_with_null_away_id():
    row = game_row({
        "id": 99, "season": 2026, "week": 1, "seasonType": "regular",
        "homeTeam": "LSU", "homeClassification": "fbs",
        "awayTeam": "Nicholls", "awayClassification": "fcs",
        "neutralSite": False, "conferenceGame": False,
        "homePoints": None, "awayPoints": None, "completed": False,
    }, TEAM_IDS)
    assert row["home_team_id"] == 1
    assert row["away_team_id"] is None
    assert row["away_school"] == "Nicholls"
    assert row["away_classification"] == "fcs"


def test_fcs_vs_fcs_dropped():
    assert game_row({
        "id": 100, "homeTeam": "Nicholls", "homeClassification": "fcs",
        "awayTeam": "McNeese", "awayClassification": "fcs",
    }, TEAM_IDS) is None


def test_field_mapping():
    row = game_row({
        "id": 101, "season": 2024, "week": 5, "seasonType": "regular",
        "homeTeam": "Alabama", "homeClassification": "fbs",
        "awayTeam": "LSU", "awayClassification": "fbs",
        "neutralSite": True, "conferenceGame": True,
        "homePoints": 30, "awayPoints": 27, "completed": True,
    }, TEAM_IDS)
    assert row["neutral_site"] is True
    assert row["conference_game"] is True
    assert row["completed"] is True
    assert row["home_points"] == 30
    assert row["home_team_id"] == 2 and row["away_team_id"] == 1
