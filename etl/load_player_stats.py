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

def fetch_player_stats_year(year: int) -> list:
    return get("/stats/player/season", year=year)

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
            s.merge(PlayerStatsOffense(**_offense_row(year, team_id, player_id, st)))

        for player_id, st in defense.items():
            s.merge(PlayerStatsDefense(**_defense_row(year, team_id, player_id, st)))

        s.commit()

def _offense_row(season: int, team_id: int, player_id: int, st: dict) -> dict:
    return {
        "season": season,
        "team_id": team_id,
        "player_id": player_id,
        "passing_yards": int(st["passing_yards"]),
        "rushing_yards": int(st["rushing_yards"]),
        "receiving_yards": int(st["receiving_yards"]),
        "total_yards": int(st["passing_yards"] + st["rushing_yards"] + st["receiving_yards"]),
        "touchdowns": int(st["touchdowns"]),
        "receptions": int(st["receptions"]),
    }

def _defense_row(season: int, team_id: int, player_id: int, st: dict) -> dict:
    return {
        "season": season,
        "team_id": team_id,
        "player_id": player_id,
        "tackles": int(st["tackles"]),
        "tackles_for_loss": st["tackles_for_loss"],
        "sacks": st["sacks"],
        "interceptions": int(st["interceptions"]),
        "touchdowns": int(st["touchdowns"]),
    }

def upsert_player_stats_year(year: int) -> None:
    rows = fetch_player_stats_year(year)

    by_team: dict[str, list] = defaultdict(list)
    for row in rows:
        by_team[row.get("team")].append(row)

    with SessionLocal() as s:
        team_ids = dict(s.query(Team.school, Team.team_id).all())

        offense_rows: dict[tuple, dict] = {}
        defense_rows: dict[tuple, dict] = {}
        skipped_schools = 0
        for school, team_rows in by_team.items():
            team_id = team_ids.get(school)
            if team_id is None:
                skipped_schools += 1
                continue
            offense, defense = _aggregate(team_rows)
            for player_id, st in offense.items():
                offense_rows[(year, team_id, player_id)] = _offense_row(year, team_id, player_id, st)
            for player_id, st in defense.items():
                defense_rows[(year, team_id, player_id)] = _defense_row(year, team_id, player_id, st)

        s.query(PlayerStatsOffense).filter(PlayerStatsOffense.season == year).delete()
        s.query(PlayerStatsDefense).filter(PlayerStatsDefense.season == year).delete()
        for model, keyed in ((PlayerStatsOffense, offense_rows), (PlayerStatsDefense, defense_rows)):
            values = list(keyed.values())
            for i in range(0, len(values), 1000):
                s.execute(model.__table__.insert(), values[i:i + 1000])
        s.commit()

    print(f"[stats] {year}: {len(offense_rows)} offense / {len(defense_rows)} defense rows, "
          f"{skipped_schools} non-FBS teams skipped")


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
            upsert_player_stats_year(y)
    elif args.all:
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
