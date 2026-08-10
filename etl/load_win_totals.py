# etl/load_win_totals.py
"""Ingest manually-collected preseason win totals from data/win_totals.csv.

School names must resolve to teams.school exactly, via data/school_aliases.csv
(columns: alias,school), or by case/punctuation-normalized match. No fuzzy
matching — any unmatched name is reported and the load exits non-zero so bad
names can't silently drop.
"""
import argparse
import csv
import re
import sys

from db.session import SessionLocal
from db.models import Team, WinTotal

def _normalize(name: str) -> str:
    return re.sub(r"[^a-z0-9]", "", name.lower())

def resolve_school(name: str, team_ids: dict[str, int], aliases: dict[str, str],
                   normalized: dict[str, int]) -> int | None:
    if name in team_ids:
        return team_ids[name]
    if name in aliases and aliases[name] in team_ids:
        return team_ids[aliases[name]]
    return normalized.get(_normalize(name))

def load_win_totals(csv_path: str, aliases_path: str | None, allow_unmatched: bool) -> None:
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

        loaded, unmatched = 0, []
        with open(csv_path, newline="", encoding="utf-8-sig") as f:
            for row in csv.DictReader(f):
                team_id = resolve_school(row["school"], team_ids, aliases, normalized)
                if team_id is None:
                    unmatched.append((row["season"], row["school"]))
                    continue
                s.merge(WinTotal(
                    season=int(row["season"]),
                    team_id=team_id,
                    win_total=float(row["win_total"]),
                    over_odds=int(row["over_odds"]) if row.get("over_odds") else None,
                    under_odds=int(row["under_odds"]) if row.get("under_odds") else None,
                    source=row.get("source") or None,
                ))
                loaded += 1
        s.commit()

    print(f"[win_totals] loaded {loaded} rows")
    if unmatched:
        print(f"UNMATCHED SCHOOLS ({len(unmatched)}) — add to data/school_aliases.csv as alias,school:")
        for season, school in unmatched:
            print(f"  {season},{school}")
        if not allow_unmatched:
            sys.exit(1)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--csv", default="data/win_totals.csv")
    parser.add_argument("--aliases", default="data/school_aliases.csv")
    parser.add_argument("--allow-unmatched", action="store_true")
    args = parser.parse_args()
    load_win_totals(args.csv, args.aliases, args.allow_unmatched)
