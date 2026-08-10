# etl/load_games.py
"""Load schedules and results from CFBD /games.

game_lines covers historical FBS-vs-FBS results but lacks neutral-site flags,
FBS-vs-FCS games, and future schedules — this table carries all three.
"""
import argparse
from db.session import SessionLocal
from db.models import Team, Game
from etl.cfbd_client import get

def game_row(game: dict, team_ids: dict[str, int]) -> dict | None:
    """Shape one /games record; None unless at least one side is FBS. Pure, for testing."""
    home_class = game.get("homeClassification")
    away_class = game.get("awayClassification")
    if home_class != "fbs" and away_class != "fbs":
        return None
    return {
        "game_id": game["id"],
        "season": game.get("season"),
        "week": game.get("week"),
        "season_type": game.get("seasonType"),
        "home_team_id": team_ids.get(game.get("homeTeam")),
        "away_team_id": team_ids.get(game.get("awayTeam")),
        "home_school": game.get("homeTeam"),
        "away_school": game.get("awayTeam"),
        "home_classification": home_class,
        "away_classification": away_class,
        "neutral_site": bool(game.get("neutralSite")),
        "conference_game": bool(game.get("conferenceGame")),
        "home_points": game.get("homePoints"),
        "away_points": game.get("awayPoints"),
        "completed": bool(game.get("completed")),
    }

def upsert_games(year: int) -> None:
    with SessionLocal() as s:
        team_ids = dict(s.query(Team.school, Team.team_id).all())

        kept = fbs_vs_fcs = skipped = 0
        for season_type in ("regular", "postseason"):
            for game in get("/games", year=year, seasonType=season_type):
                row = game_row(game, team_ids)
                if row is None:
                    skipped += 1
                    continue
                s.merge(Game(**row))
                kept += 1
                if row["home_classification"] != row["away_classification"]:
                    fbs_vs_fcs += 1
        s.commit()
    print(f"[games] {year}: kept {kept} ({fbs_vs_fcs} cross-division), skipped {skipped} non-FBS")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--year", type=int, action="append", help="Season(s) to load.")
    args = parser.parse_args()
    for y in args.year or [2026]:
        upsert_games(y)
