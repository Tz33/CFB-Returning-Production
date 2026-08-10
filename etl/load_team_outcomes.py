# etl/load_team_outcomes.py
import argparse
from db.session import SessionLocal
from db.models import Team, TeamOutcome
from etl.cfbd_client import get

def fetch_records(year: int) -> list:
    return get("/records", year=year)

def fetch_sp_ratings(year: int) -> list:
    return get("/ratings/sp", year=year)

def upsert_team_outcomes(year: int) -> None:
    records = fetch_records(year)
    sp_ratings = fetch_sp_ratings(year)

    with SessionLocal() as s:
        team_ids = dict(s.query(Team.school, Team.team_id).all())

        outcomes: dict[int, TeamOutcome] = {}
        skipped: set[str] = set()

        for row in records:
            school = row.get("team")
            team_id = team_ids.get(school)
            if team_id is None:
                skipped.add(school)
                continue
            total = row.get("total") or {}
            wins = total.get("wins")
            losses = total.get("losses")
            games = total.get("games") or ((wins or 0) + (losses or 0) + (total.get("ties") or 0))
            outcomes[team_id] = TeamOutcome(
                season=year,
                team_id=team_id,
                wins=wins,
                losses=losses,
                win_pct=(wins / games) if games and wins is not None else None,
            )

        for row in sp_ratings:
            school = row.get("team")
            # /ratings/sp includes a "nationalAverages" pseudo-row; the school map also drops it
            team_id = team_ids.get(school)
            if team_id is None:
                if school != "nationalAverages":
                    skipped.add(school)
                continue
            outcome = outcomes.get(team_id)
            if outcome is None:
                outcome = TeamOutcome(season=year, team_id=team_id)
                outcomes[team_id] = outcome
            outcome.sp_rating = row.get("rating")

        for outcome in outcomes.values():
            s.merge(outcome)
        s.commit()

    print(f"[outcomes] {year}: {len(outcomes)} teams, skipped {len(skipped)} unknown schools")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--year", type=int, action="append", help="Season(s) to load. Use multiple --year flags.")
    args = parser.parse_args()

    for y in args.year or [2024]:
        upsert_team_outcomes(y)
