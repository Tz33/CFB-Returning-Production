# etl/load_rosters.py
import argparse
from db.session import SessionLocal
from db.models import Team, Roster
from etl.cfbd_client import get

def fetch_roster(team: str, year: int):
    return get("/roster", year=year, team=team)

def fetch_roster_year(year: int):
    return get("/roster", year=year)

def _parse_player(p: dict, season: int, team_id: int) -> dict | None:
    if p.get("id") in (None, ""):
        return None
    player_cfbd_id = int(p["id"])

    # Build a reliable full name from available keys
    first = p.get("first_name") or p.get("firstName") or ""
    last  = p.get("last_name")  or p.get("lastName")  or ""
    name  = (p.get("name") or f"{first} {last}").strip()

    jersey_val = p.get("jersey") or p.get("jersey_number")  # just in case
    jersey = int(jersey_val) if jersey_val not in (None, "", "0") else None

    return {
        "season": season,
        "team_id": team_id,
        "player_id": player_cfbd_id,
        "full_name": name,
        "position": p.get("position"),
        "jersey": jersey,
        "player_cfbd_id": player_cfbd_id,
    }

def upsert_roster(team: str, year: int, team_id: int | None = None):
    rows = fetch_roster(team, year)
    with SessionLocal() as s:
        if team_id is None:
            team_id = s.query(Team.team_id).filter(Team.school == team).scalar()
            if not team_id:
                raise RuntimeError(f"Team not found in DB: {team}")

        for p in rows:
            parsed = _parse_player(p, year, team_id)
            if parsed is None:
                continue

            obj = s.get(Roster, (year, team_id, parsed["player_id"]))
            if not obj:
                s.add(Roster(**parsed))
            else:
                obj.full_name = parsed["full_name"]
                obj.position = parsed["position"]
                obj.jersey = parsed["jersey"]
                obj.player_cfbd_id = parsed["player_cfbd_id"]

        s.commit()

def upsert_roster_year(year: int):
    rows = fetch_roster_year(year)
    with SessionLocal() as s:
        team_ids = dict(s.query(Team.school, Team.team_id).all())

        # dedupe on the composite PK; the year-only endpoint includes non-FBS teams (skipped)
        parsed: dict[tuple, dict] = {}
        skipped_schools = 0
        for p in rows:
            team_id = team_ids.get(p.get("team"))
            if team_id is None:
                skipped_schools += 1
                continue
            row = _parse_player(p, year, team_id)
            if row is not None:
                parsed[(row["season"], row["team_id"], row["player_id"])] = row

        s.query(Roster).filter(Roster.season == year).delete()
        values = list(parsed.values())
        for i in range(0, len(values), 1000):
            s.execute(Roster.__table__.insert(), values[i:i + 1000])
        s.commit()

    print(f"[rosters] {year}: {len(parsed)} players inserted, {skipped_schools} non-FBS rows skipped")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--team", help="Exact school name (e.g., 'LSU'). If omitted and --all is used, loads every team.")
    parser.add_argument("--year", type=int, action="append", help="Season(s) to load. Use multiple --year flags, e.g., --year 2024 --year 2025")
    parser.add_argument("--all", action="store_true", help="Load all teams from the teams table")
    parser.add_argument("--bulk", action="store_true", help="One API call per year covering every team (fastest)")
    args = parser.parse_args()

    years = args.year or [2024, 2025]  # default seasons

    if args.bulk:
        for y in years:
            upsert_roster_year(y)
    elif args.all:
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

