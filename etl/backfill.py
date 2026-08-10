# etl/backfill.py
"""One-shot historical backfill: teams, rosters, stats, outcomes, then metrics.

Each stage is idempotent (per-season delete+insert or merges), so a crashed
run can be resumed with --only / --skip.
"""
import argparse
import time
import httpx

from db.metrics import refresh_materialized_views
from etl import compute_incoming, compute_returning, compute_returning_detail, load_teams
from etl.load_player_stats import upsert_player_stats_year
from etl.load_rosters import upsert_roster_year
from etl.load_team_outcomes import upsert_team_outcomes

STAGES = ["teams", "rosters", "stats", "outcomes", "refresh", "returning", "returning_detail", "incoming"]

def _with_retry(fn, *args, attempts: int = 3):
    for attempt in range(1, attempts + 1):
        try:
            return fn(*args)
        except httpx.HTTPError as e:
            if attempt == attempts:
                raise
            status = getattr(getattr(e, "response", None), "status_code", None)
            wait = 60 if status == 429 else 5 * attempt
            print(f"  retry {attempt}/{attempts - 1} in {wait}s ({e})")
            time.sleep(wait)

def main(start_year: int, end_year: int, stages: list[str]) -> None:
    years = list(range(start_year, end_year + 1))
    # metrics need a prior season, so the first usable season is start_year + 1
    metric_seasons = years[1:]

    if "teams" in stages:
        for y in years:
            print(f"[teams] {y}")
            _with_retry(load_teams.main, y)
            time.sleep(1)

    for stage, loader in (("rosters", upsert_roster_year),
                          ("stats", upsert_player_stats_year),
                          ("outcomes", upsert_team_outcomes)):
        if stage in stages:
            for y in years:
                _with_retry(loader, y)
                time.sleep(1)

    if "refresh" in stages:
        print("[refresh] materialized views")
        refresh_materialized_views()

    if "returning" in stages:
        compute_returning.run(seasons=metric_seasons)

    if "returning_detail" in stages:
        compute_returning_detail.run(seasons=metric_seasons)

    if "incoming" in stages:
        compute_incoming.run(seasons=metric_seasons)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--start-year", type=int, default=2014)
    parser.add_argument("--end-year", type=int, default=2025)
    parser.add_argument("--only", action="append", choices=STAGES, help="Run only these stage(s)")
    parser.add_argument("--skip", action="append", choices=STAGES, default=[], help="Skip these stage(s)")
    args = parser.parse_args()

    selected = [s for s in (args.only or STAGES) if s not in args.skip]
    print(f"[backfill] {args.start_year}-{args.end_year}, stages: {', '.join(selected)}")
    main(args.start_year, args.end_year, selected)
