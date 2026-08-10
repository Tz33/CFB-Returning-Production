import os
import httpx
from dotenv import load_dotenv

load_dotenv()
BASE = "https://api.collegefootballdata.com"
API_KEY = os.getenv("CFBD_API_KEY")
HEADERS = {"Authorization": f"Bearer {API_KEY}"} if API_KEY else {}

def get(path: str, **params):
    with httpx.Client(headers=HEADERS, timeout=30) as c:
        r = c.get(f"{BASE}{path}", params=params)
        r.raise_for_status()
        return r.json()

def get_fbs_teams(year: int = 2024):
    return get("/teams/fbs", year=year)

