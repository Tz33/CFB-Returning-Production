# etl/load_coach_changes.py
"""Flag new-head-coach seasons per team from CFBD coach tenures.

Uses /coaches/tenures (tenure startYear boundaries, isInterim) — never the
deprecated hireDate field on /coaches, which is null for many records.
"""
import argparse
import time

from db.session import SessionLocal
from db.models import Team, CoachChange
from etl.cfbd_client import get

def fetch_tenures(team: str) -> list:
    return get("/coaches/tenures", team=team)

def _tenure_year(tenure: dict, field: str, effective_field: str) -> int | None:
    year = tenure.get(field)
    if year is not None:
        return int(year)
    effective = tenure.get(effective_field)
    if effective:
        return int(str(effective)[:4])
    return None

def _coach_name(tenure: dict) -> str | None:
    coach = tenure.get("coach")
    source = coach if isinstance(coach, dict) else tenure
    first = source.get("firstName") or ""
    last = source.get("lastName") or ""
    return f"{first} {last}".strip() or None

def seasons_with_new_coach(tenures: list, start: int, end: int) -> dict[int, dict]:
    """Per-season coach-change flags from a team's tenure list. Pure, for testing."""
    result = {}
    for season in range(start, end + 1):
        starting = [t for t in tenures if _tenure_year(t, "startYear", "effectiveStart") == season]
        covering = [
            t for t in tenures
            if (s := _tenure_year(t, "startYear", "effectiveStart")) is not None
            and s <= season
            and ((e := _tenure_year(t, "endYear", "effectiveEnd")) is None or e >= season)
        ]
        current = max(covering, key=lambda t: _tenure_year(t, "startYear", "effectiveStart") or 0, default=None)
        result[season] = {
            "new_head_coach": bool(starting),
            "is_interim": (any(bool(t.get("isInterim")) for t in starting)
                           if starting else bool(current and current.get("isInterim"))),
            "coach_name": _coach_name(current) if current else None,
            "tenure_start_year": _tenure_year(current, "startYear", "effectiveStart") if current else None,
        }
    return result

def load_coach_changes(start_year: int, end_year: int) -> None:
    with SessionLocal() as s:
        teams = s.query(Team.school, Team.team_id).order_by(Team.school).all()

        new_counts: dict[int, int] = {}
        for school, team_id in teams:
            tenures = fetch_tenures(school)
            flags = seasons_with_new_coach(tenures, start_year, end_year)
            for season, info in flags.items():
                s.merge(CoachChange(season=season, team_id=team_id, **info))
                if info["new_head_coach"]:
                    new_counts[season] = new_counts.get(season, 0) + 1
            time.sleep(1)
        s.commit()

    for season in sorted(new_counts):
        print(f"[coaches] {season}: {new_counts[season]} new head coaches")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--start-year", type=int, default=2014)
    parser.add_argument("--end-year", type=int, default=2025)
    args = parser.parse_args()
    load_coach_changes(args.start_year, args.end_year)
