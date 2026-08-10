# etl/load_game_lines.py
"""Load per-game betting lines from CFBD /lines (2013+).

Provider coverage churns over the years (consensus/numberfire/teamrankings
through ~2021, then Bovada/DraftKings/ESPN Bet), so lines are picked by
preference order with a first-non-null-spread fallback.
"""
import argparse
from db.session import SessionLocal
from db.models import Team, GameLine
from etl.cfbd_client import get

PROVIDER_PREFERENCE = ["consensus", "Bovada", "DraftKings", "ESPN Bet", "teamrankings", "numberfire"]

def pick_line(lines: list) -> dict | None:
    """Preferred provider with a non-null spread, else any line with a spread."""
    with_spread = [l for l in lines if l.get("spread") is not None]
    if not with_spread:
        return None
    by_provider = {l.get("provider"): l for l in with_spread}
    for provider in PROVIDER_PREFERENCE:
        if provider in by_provider:
            return by_provider[provider]
    return with_spread[0]

def upsert_game_lines(year: int) -> None:
    games = get("/lines", year=year)
    with SessionLocal() as s:
        team_ids = dict(s.query(Team.school, Team.team_id).all())

        kept = skipped_no_line = 0
        for game in games:
            line = pick_line(game.get("lines") or [])
            if line is None:
                skipped_no_line += 1
                continue
            spread = line.get("spread")
            s.merge(GameLine(
                game_id=game["id"],
                season=game.get("season") or year,
                week=game.get("week"),
                season_type=game.get("seasonType"),
                home_team_id=team_ids.get(game.get("homeTeam")),
                away_team_id=team_ids.get(game.get("awayTeam")),
                home_score=game.get("homeScore"),
                away_score=game.get("awayScore"),
                spread=float(spread) if spread is not None else None,
                spread_open=(float(line["spreadOpen"]) if line.get("spreadOpen") is not None else None),
                over_under=(float(line["overUnder"]) if line.get("overUnder") is not None else None),
                provider=line.get("provider"),
            ))
            kept += 1
        s.commit()
    print(f"[lines] {year}: {kept} games with a spread, {skipped_no_line} without")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--year", type=int, action="append", help="Season(s) to load.")
    args = parser.parse_args()
    for y in args.year or [2024]:
        upsert_game_lines(y)
