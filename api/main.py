from fastapi import FastAPI, HTTPException
from db.session import SessionLocal
from db.models import Team, ReturningSummary, IncomingSummary

app = FastAPI(title="CFB Returning Value API")

@app.get("/health")

def health():
    return {"status": "ok"}

@app.get("/teams")
def list_teams():
    with SessionLocal() as s:
        rows = s.query(Team).order_by(Team.school).all()
        return [{"team_id": t.team_id, "school": t.school, "conference": t.conference} for t in rows]


@app.get("/returning/{team_id}/{season}")
def get_returning_summary(team_id: int, season: int):
    with SessionLocal() as s:
        summary = (
            s.query(ReturningSummary)
            .filter(ReturningSummary.team_id == team_id, ReturningSummary.season == season)
            .one_or_none()
        )

        if summary is None:
            raise HTTPException(status_code=404, detail="Returning summary not found")

        return {
            "team_id": team_id,
            "season": season,
            "off_pct": summary.off_pct,
            "def_pct": summary.def_pct,
            "overall_pct": summary.overall_pct,
        }


@app.get("/incoming/{team_id}/{season}")
def get_incoming_summary(team_id: int, season: int):
    with SessionLocal() as s:
        summary = (
            s.query(IncomingSummary)
            .filter(IncomingSummary.team_id == team_id, IncomingSummary.season == season)
            .one_or_none()
        )

        if summary is None:
            raise HTTPException(status_code=404, detail="Incoming summary not found")

        return {
            "team_id": team_id,
            "season": season,
            "transfer_share": summary.transfer_share,
            "freshman_count": summary.freshman_count,
        }


