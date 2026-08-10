# etl/load_rosters.py
import argparse
from db.session import SessionLocal
from db.models import Team, Roster
from etl.cfbd_client import get

def fetch_roster(team: str, year: int):
    return get("/roster", year=year, team=team)

def upsert_roster(team: str, year: int, team_id: int | None = None):
    rows = fetch_roster(team, year)
    with SessionLocal() as s:
        if team_id is None:
            team_id = s.query(Team.team_id).filter(Team.school == team).scalar()
            if not team_id:
                raise RuntimeError(f"Team not found in DB: {team}")

        # inside upsert_roster(...)
        for p in rows:
            player_cfbd_id = int(p["id"])

            # Build a reliable full name from available keys
            first = p.get("first_name") or p.get("firstName") or ""
            last  = p.get("last_name")  or p.get("lastName")  or ""
            name  = (p.get("name") or f"{first} {last}").strip()

            jersey_val = p.get("jersey") or p.get("jersey_number")  # just in case
            jersey = int(jersey_val) if jersey_val not in (None, "", "0") else None

            identity = (year, team_id, player_cfbd_id)
            obj = s.get(Roster, identity)
            if not obj:
                obj = Roster(
                    season=year,
                    team_id=team_id,
                    player_id=player_cfbd_id,
                    full_name=name,
                    position=p.get("position"),
                    jersey=jersey,
                    player_cfbd_id=player_cfbd_id,
                )
                s.add(obj)
            else:
                obj.full_name = name
                obj.position = p.get("position")
                obj.jersey = jersey
                obj.player_cfbd_id = player_cfbd_id

        s.commit()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--team", help="Exact school name (e.g., 'LSU'). If omitted and --all is used, loads every team.")
    parser.add_argument("--year", type=int, action="append", help="Season(s) to load. Use multiple --year flags, e.g., --year 2024 --year 2025")
    parser.add_argument("--all", action="store_true", help="Load all teams from the teams table")
    args = parser.parse_args()

    years = args.year or [2024, 2025]  # default seasons

    if args.all:
        # load every team from DB
        with SessionLocal() as s:
            teams = s.query(Team.school, Team.team_id).order_by(Team.school).all()
        for school, tid in teams:
            for y in years:
                print(f"[load] {school} {y}")
                upsert_roster(school, y, team_id=tid)
    else:
        if not args.team:
            raise SystemExit("Provide --team 'School Name' OR use --all")
        for y in years:
            print(f"[load] {args.team} {y}")
            upsert_roster(args.team, y)

