# etl/load_team_seasons.py
"""Per-season conference membership from /teams/fbs — teams.conference only
holds the latest affiliation, which is wrong historically post-realignment."""
import argparse
from db.session import SessionLocal
from db.models import Team, TeamSeason
from etl.cfbd_client import get

def upsert_team_seasons(year: int) -> None:
    rows = get("/teams/fbs", year=year)
    with SessionLocal() as s:
        team_ids = dict(s.query(Team.school, Team.team_id).all())
        skipped = 0
        for row in rows:
            team_id = team_ids.get(row.get("school"))
            if team_id is None:
                skipped += 1
                continue
            s.merge(TeamSeason(
                season=year,
                team_id=team_id,
                conference=row.get("conference"),
                classification=row.get("classification") or "fbs",
            ))
        s.commit()
    print(f"[team_seasons] {year}: {len(rows) - skipped} teams, {skipped} unknown skipped")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--year", type=int, action="append", help="Season(s) to load.")
    args = parser.parse_args()
    for y in args.year or [2024]:
        upsert_team_seasons(y)
