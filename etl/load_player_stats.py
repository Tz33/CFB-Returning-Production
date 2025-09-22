import os
import httpx
from dotenv import load_dotenv
from db.session import SessionLocal
from db.models import PlayerStatsOffense, PlayerStatsDefense

load_dotenv()
API_KEY = os.getenv("CFBD_API_KEY")
BASE_URL = "https://api.collegefootballdata.com"

async def fetch_player_stats(season, team):
    # Fetch offensive and defensive stats for each player on the team
    response_offense = await httpx.get(f"{BASE_URL}/stats/player/season", params={
        "team": team,
        "year": season,
        "offense": True,
        "apiKey": API_KEY
    })
    response_defense = await httpx.get(f"{BASE_URL}/stats/player/season", params={
        "team": team,
        "year": season,
        "defense": True,
        "apiKey": API_KEY
    })

    offense_data = response_offense.json()
    defense_data = response_defense.json()

    return offense_data, defense_data

def upsert_player_stats(team: str, year: int, offense_data: list, defense_data: list):
    with SessionLocal() as s:
        # Look up numeric team_id for this school name
        team_id = s.query(Team.team_id).filter(Team.school == team).scalar()
        if not team_id:
            raise RuntimeError(f"Team not found in DB: {team}")

        # Insert offense stats
        for player in offense_data:
            obj = PlayerStatsOffense(
                season=year,
                team_id=team_id,
                player_id=player["playerId"],
                passing_yards=player.get("passingYards", 0),
                rushing_yards=player.get("rushingYards", 0),
                receiving_yards=player.get("receivingYards", 0),
                total_yards=player.get("totalYards", 0),
                touchdowns=player.get("touchdowns", 0),
                receptions=player.get("receptions", 0),
            )
            s.merge(obj)   # merge = insert or update

        # Insert defense stats
        for player in defense_data:
            obj = PlayerStatsDefense(
                season=year,
                team_id=team_id,
                player_id=player["playerId"],
                tackles=player.get("tackles", 0),
                sacks=player.get("sacks", 0),
                interceptions=player.get("interceptions", 0),
                tackles_for_loss=player.get("tacklesForLoss", 0),
                touchdowns=player.get("touchdowns", 0),
            )
            s.merge(obj)

        s.commit()

