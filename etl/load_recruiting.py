# etl/load_recruiting.py
"""Team recruiting class rank/points from CFBD /recruiting/teams.

Raw points are stored as-is; the points scale drifts across eras, so
normalization (within-season z-score) happens at model-fit time, not here.
"""
import argparse
import re
from db.session import SessionLocal
from db.models import Team, TeamSeason, Recruiting
from etl.cfbd_client import get

def _normalize(name: str) -> str:
    return re.sub(r"[^a-z0-9]", "", name.lower())

def upsert_recruiting(year: int) -> None:
    rows = get("/recruiting/teams", year=year)
    with SessionLocal() as s:
        team_ids = dict(s.query(Team.school, Team.team_id).all())
        normalized = {_normalize(school): tid for school, tid in team_ids.items()}
        fbs_ids = {tid for (tid,) in s.query(TeamSeason.team_id).filter(TeamSeason.season == year)}

        kept = skipped = 0
        for row in rows:
            name = row.get("team") or ""
            team_id = team_ids.get(name) or normalized.get(_normalize(name))
            if team_id is None or team_id not in fbs_ids:
                skipped += 1  # FCS programs in the recruiting feed
                continue
            s.merge(Recruiting(
                season=year,
                team_id=team_id,
                rank=row.get("rank"),
                points=row.get("points"),
            ))
            kept += 1
        s.commit()
    print(f"[recruiting] {year}: {kept} FBS teams, {skipped} non-FBS skipped")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--year", type=int, action="append", help="Season(s) to load.")
    args = parser.parse_args()
    for y in args.year or [2026]:
        upsert_recruiting(y)
