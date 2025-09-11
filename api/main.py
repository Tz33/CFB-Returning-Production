from fastapi import FastAPI
from db.session import SessionLocal
from db.models import Team

app = FastAPI(title="CFB Returning Value API")

@app.get("/health")

def health():
    return {"status": "ok"}

@app.get("/teams")
def list_teams():
    with SessionLocal() as s:
        rows = s.query(Team).order_by(Team.school).all()
        return [{"team_id": t.team_id, "school": t.school, "conference": t.conference} for t in rows]


