# etl/load_participation.py
"""Ingest per-player GP/GS participation data from data/participation/*.csv.

CSV columns: season,school,player_name,class_year,position,gp,gs
(one file per season is the convention, but any split works — rows carry
their own season). Rows come from stats.ncaa.org team rosters via
etl/scrape_ncaa_participation.js, or from any manual source.

School names must resolve to teams.school exactly, via data/school_aliases.csv
(columns: alias,school), or by case/punctuation-normalized match. No fuzzy
matching — any unmatched name is reported and the load exits non-zero so bad
names can't silently drop.
"""
import argparse
import csv
import glob
import sys

from db.session import SessionLocal
from db.models import PlayerParticipation, Team
from etl.load_win_totals import _normalize, resolve_school


def load_participation(csv_paths: list[str], aliases_path: str | None,
                       allow_unmatched: bool, source: str) -> None:
    aliases: dict[str, str] = {}
    if aliases_path:
        try:
            with open(aliases_path, newline="", encoding="utf-8-sig") as f:
                aliases = {row["alias"]: row["school"] for row in csv.DictReader(f)}
        except FileNotFoundError:
            pass

    with SessionLocal() as s:
        team_ids = dict(s.query(Team.school, Team.team_id).all())
        normalized = {_normalize(school): tid for school, tid in team_ids.items()}

        loaded, unmatched = 0, set()
        for path in csv_paths:
            with open(path, newline="", encoding="utf-8-sig") as f:
                for row in csv.DictReader(f):
                    team_id = resolve_school(row["school"], team_ids, aliases, normalized)
                    if team_id is None:
                        unmatched.add((row["season"], row["school"]))
                        continue
                    s.merge(PlayerParticipation(
                        season=int(row["season"]),
                        team_id=team_id,
                        player_name=row["player_name"].strip(),
                        class_year=row.get("class_year") or None,
                        position=row.get("position") or None,
                        games_played=int(row["gp"] or 0),
                        games_started=int(row["gs"] or 0),
                        source=row.get("source") or source,
                    ))
                    loaded += 1
        s.commit()

    print(f"[participation] loaded {loaded} rows from {len(csv_paths)} file(s)")
    if unmatched:
        print(f"UNMATCHED SCHOOLS ({len(unmatched)}) — add to data/school_aliases.csv as alias,school:")
        for season, school in sorted(unmatched):
            print(f"  {season},{school}")
        if not allow_unmatched:
            sys.exit(1)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--csv", action="append",
                        help="CSV path(s); defaults to data/participation/*.csv")
    parser.add_argument("--aliases", default="data/school_aliases.csv")
    parser.add_argument("--allow-unmatched", action="store_true")
    parser.add_argument("--source", default="ncaa")
    args = parser.parse_args()
    paths = args.csv or sorted(glob.glob("data/participation/*.csv"))
    if not paths:
        sys.exit("no participation CSVs found (data/participation/*.csv)")
    load_participation(paths, args.aliases, args.allow_unmatched, args.source)
