# etl/load_player_stats.py
import argparse
from collections import defaultdict
from db.session import SessionLocal
from db.models import Team, PlayerStatsOffense, PlayerStatsDefense
from etl.cfbd_client import get

# CFBD /stats/player/season returns long-format rows:
#   {"playerId": "4426333", "category": "passing", "statType": "YDS", "stat": "3812", ...}
# Map (category, statType) pairs onto our wide columns. Touchdowns accumulate
# across categories, so aggregation below uses += throughout.
OFFENSE_FIELDS = {
    ("passing", "YDS"): "passing_yards",
    ("rushing", "YDS"): "rushing_yards",
    ("receiving", "YDS"): "receiving_yards",
    ("receiving", "REC"): "receptions",
    ("passing", "TD"): "touchdowns",
    ("rushing", "TD"): "touchdowns",
    ("receiving", "TD"): "touchdowns",
}
DEFENSE_FIELDS = {
    ("defensive", "TOT"): "tackles",
    ("defensive", "TFL"): "tackles_for_loss",
    ("defensive", "SACKS"): "sacks",
    ("defensive", "TD"): "touchdowns",
    ("interceptions", "INT"): "interceptions",
    ("interceptions", "TD"): "touchdowns",
}

def fetch_player_stats(team: str, year: int) -> list:
    return get("/stats/player/season", year=year, team=team)

def _aggregate(rows: list):
    offense = defaultdict(lambda: defaultdict(float))
    defense = defaultdict(lambda: defaultdict(float))
    for row in rows:
        try:
            player_id = int(row["playerId"])
            value = float(row["stat"])
        except (KeyError, TypeError, ValueError):
            continue  # skip team pseudo-players / non-numeric stats
        key = (row.get("category"), row.get("statType"))
        if key in OFFENSE_FIELDS:
            offense[player_id][OFFENSE_FIELDS[key]] += value
        if key in DEFENSE_FIELDS:
            defense[player_id][DEFENSE_FIELDS[key]] += value
    return offense, defense

def upsert_player_stats(team: str, year: int, team_id: int | None = None):
    rows = fetch_player_stats(team, year)
    offense, defense = _aggregate(rows)

    with SessionLocal() as s:
        if team_id is None:
            team_id = s.query(Team.team_id).filter(Team.school == team).scalar()
            if not team_id:
                raise RuntimeError(f"Team not found in DB: {team}")

        for player_id, st in offense.items():
            s.merge(PlayerStatsOffense(
                season=year,
                team_id=team_id,
                player_id=player_id,
                passing_yards=int(st["passing_yards"]),
                rushing_yards=int(st["rushing_yards"]),
                receiving_yards=int(st["receiving_yards"]),
                total_yards=int(st["passing_yards"] + st["rushing_yards"] + st["receiving_yards"]),
                touchdowns=int(st["touchdowns"]),
                receptions=int(st["receptions"]),
            ))

        for player_id, st in defense.items():
            s.merge(PlayerStatsDefense(
                season=year,
                team_id=team_id,
                player_id=player_id,
                tackles=int(st["tackles"]),
                tackles_for_loss=st["tackles_for_loss"],
                sacks=st["sacks"],
                interceptions=int(st["interceptions"]),
                touchdowns=int(st["touchdowns"]),
            ))

        s.commit()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--team", help="Exact school name (e.g., 'LSU'). If omitted and --all is used, loads every team.")
    parser.add_argument("--year", type=int, action="append", help="Season(s) to load. Use multiple --year flags, e.g., --year 2024 --year 2025")
    parser.add_argument("--all", action="store_true", help="Load all teams from the teams table")
    args = parser.parse_args()

    years = args.year or [2024, 2025]  # default seasons

    if args.all:
        with SessionLocal() as s:
            teams = s.query(Team.school, Team.team_id).order_by(Team.school).all()
        for school, tid in teams:
            for y in years:
                print(f"[load] {school} {y}")
                upsert_player_stats(school, y, team_id=tid)
    else:
        if not args.team:
            raise SystemExit("Provide --team 'School Name' OR use --all")
        for y in years:
            print(f"[load] {args.team} {y}")
            upsert_player_stats(args.team, y)
