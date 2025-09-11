# etl/load_rosters.py
import os, httpx
from dotenv import load_dotenv
from db.session import SessionLocal
from db.models import Team, Roster

load_dotenv()
BASE = "https://api.collegefootballdata.com"
HEADERS = {"Authorization": f"Bearer {os.getenv('CFBD_API_KEY')}"}

def fetch_roster(team: str, year: int):
    r = httpx.get(f"{BASE}/roster", params={"year": year, "team": team}, headers=HEADERS, timeout=30)
    r.raise_for_status()
    return r.json()

def upsert_roster(team: str, year: int):
    rows = fetch_roster(team, year)
    with SessionLocal() as s:
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
    # example: load LSU for 2024 (Y-1) and 2025 (Y)
    for y in (2024, 2025):
        upsert_roster("LSU", y)
