# etl/load_teams.py
from db.session import SessionLocal
from db.models import Team
from etl.cfbd_client import get_fbs_teams

def main(year: int = 2024):
    teams = get_fbs_teams(year)
    with SessionLocal() as s:
        for t in teams:
            # upsert by school
            existing = s.query(Team).filter_by(school=t["school"]).one_or_none()
            if existing:
                existing.conference = t.get("conference")
            else:
                s.add(Team(school=t["school"], conference=t.get("conference")))
        s.commit()

if __name__ == "__main__":
    main(2024)
