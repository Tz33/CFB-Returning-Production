"""Load player stats from the CFBD API into the database."""
from __future__ import annotations

import argparse
import os
from collections.abc import Iterable
from typing import Any

import httpx
from dotenv import load_dotenv

from db.models import PlayerStatsDefense, PlayerStatsOffense, Team
from db.session import SessionLocal

load_dotenv()

BASE_URL = "https://api.collegefootballdata.com"
API_KEY = os.getenv("CFBD_API_KEY")
if not API_KEY:
    raise RuntimeError("CFBD_API_KEY not set. Add it to your environment or .env file.")

HEADERS = {"Authorization": f"Bearer {API_KEY}"}
TIMEOUT = 60

OFFENSE_FIELD_ALIASES: dict[str, list[str]] = {
    "passing_yards": [
        "passing_yards",
        "passingYards",
        "passYards",
        "passYds",
        "pass",
        "passing",
        "passyards",
    ],
    "rushing_yards": [
        "rushing_yards",
        "rushingYards",
        "rushYards",
        "rushYds",
        "rush",
        "rushing",
        "rushyards",
    ],
    "receiving_yards": [
        "receiving_yards",
        "receivingYards",
        "recYards",
        "recYds",
        "receiving",
        "receivingyards",
    ],
    "total_yards": [
        "total_yards",
        "totalYards",
        "totalyards",
        "allPurposeYards",
        "allpurposeyards",
        "allPurpose",
        "total",
    ],
    "touchdowns": [
        "touchdowns",
        "touchdown",
        "td",
        "passTouchdowns",
        "rushingTouchdowns",
        "receivingTouchdowns",
        "passingTouchdowns",
        "rushTouchdowns",
        "recTouchdowns",
        "totalTouchdowns",
        "touchdownsTotal",
    ],
    "receptions": ["receptions", "reception", "catches", "recs"],
}

DEFENSE_FIELD_ALIASES: dict[str, list[str]] = {
    "tackles": ["tackles", "totalTackles", "totaltackles"],
    "tackles_for_loss": [
        "tackles_for_loss",
        "tacklesForLoss",
        "tfl",
        "tackles-for-loss",
    ],
    "sacks": ["sacks", "sack"],
    "interceptions": ["interceptions", "ints"],
    "touchdowns": ["touchdowns", "touchdown", "td", "defensiveTouchdowns"],
}


def _normalize_aliases(field_aliases: dict[str, list[str]]) -> dict[str, str]:
    """Map normalized alias keys to the target column name."""
    normalized: dict[str, str] = {}
    for column, aliases in field_aliases.items():
        normalized[column] = column
        for alias in aliases:
            normalized[alias.lower()] = column
    return normalized


OFFENSE_ALIAS_LOOKUP = _normalize_aliases(OFFENSE_FIELD_ALIASES)
DEFENSE_ALIAS_LOOKUP = _normalize_aliases(DEFENSE_FIELD_ALIASES)


def _to_int(value: Any) -> int:
    if value in (None, "", "null"):
        return 0
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, (int, float)):
        return int(value)
    try:
        return int(float(str(value)))
    except (TypeError, ValueError):
        return 0


def _player_id_from_row(row: dict[str, Any]) -> int | None:
    for key in ("playerId", "player_id", "id", "athleteId", "playerid"):
        if key in row and row[key] not in (None, ""):
            try:
                return int(row[key])
            except (TypeError, ValueError):
                continue
    return None


def _apply_direct_fields(
    row: dict[str, Any],
    entry: dict[str, int],
    field_aliases: dict[str, list[str]],
) -> None:
    for column, aliases in field_aliases.items():
        for alias in aliases:
            if alias in row and row[alias] not in (None, ""):
                entry[column] = _to_int(row[alias])
                break


def _apply_category_fields(
    categories: Iterable[Any],
    entry: dict[str, int],
    alias_lookup: dict[str, str],
) -> None:
    for item in categories:
        if not isinstance(item, dict):
            continue
        name = (
            item.get("name")
            or item.get("statType")
            or item.get("category")
            or item.get("statName")
            or ""
        )
        value = item.get("stat") or item.get("value") or item.get("statValue")
        if not name or value in (None, ""):
            continue
        column = alias_lookup.get(str(name).lower())
        if column:
            entry[column] = _to_int(value)


def _apply_stat_field(
    row: dict[str, Any],
    entry: dict[str, int],
    alias_lookup: dict[str, str],
) -> None:
    stat_type = row.get("statType") or row.get("category") or row.get("statCategory")
    stat_value = row.get("stat") or row.get("value")
    if not stat_type or stat_value in (None, ""):
        return
    column = alias_lookup.get(str(stat_type).lower())
    if column:
        entry[column] += _to_int(stat_value)


def _aggregate_stats(
    rows: Iterable[dict[str, Any]],
    field_aliases: dict[str, list[str]],
    alias_lookup: dict[str, str],
) -> dict[int, dict[str, int]]:
    results: dict[int, dict[str, int]] = {}
    for row in rows:
        if not isinstance(row, dict):
            continue
        player_id = _player_id_from_row(row)
        if player_id is None:
            continue
        entry = results.setdefault(
            player_id, {column: 0 for column in field_aliases.keys()}
        )
        _apply_direct_fields(row, entry, field_aliases)
        categories = row.get("categories") or row.get("stats") or row.get("playerStats")
        if isinstance(categories, dict):
            category_iter = categories.values()
        elif isinstance(categories, Iterable) and not isinstance(categories, (str, bytes)):
            category_iter = categories
        else:
            category_iter = None
        if category_iter is not None:
            _apply_category_fields(category_iter, entry, alias_lookup)
        _apply_stat_field(row, entry, alias_lookup)
    return results


def fetch_player_stats(
    client: httpx.Client, *, year: int, team: str, offense: bool
) -> list[dict[str, Any]]:
    params = {"year": year, "team": team}
    params["offense" if offense else "defense"] = True
    response = client.get(f"{BASE_URL}/stats/player/season", params=params)
    response.raise_for_status()
    data = response.json()
    if isinstance(data, dict):
        # Some CFBD responses wrap results in a "data" field.
        data = data.get("data", [])
    if not isinstance(data, list):
        raise RuntimeError("Unexpected response format from CFBD API")
    return data


def load_stats_for_team(client: httpx.Client, *, year: int, team_name: str) -> None:
    offense_rows = fetch_player_stats(client, year=year, team=team_name, offense=True)
    defense_rows = fetch_player_stats(client, year=year, team=team_name, offense=False)

    offense_stats = _aggregate_stats(
        offense_rows, OFFENSE_FIELD_ALIASES, OFFENSE_ALIAS_LOOKUP
    )
    defense_stats = _aggregate_stats(
        defense_rows, DEFENSE_FIELD_ALIASES, DEFENSE_ALIAS_LOOKUP
    )

    with SessionLocal() as session:
        team_id = (
            session.query(Team.team_id).filter(Team.school == team_name).scalar()
        )
        if team_id is None:
            raise RuntimeError(f"Team not found in database: {team_name}")

        for player_id, stats in offense_stats.items():
            obj = PlayerStatsOffense(
                season=year,
                team_id=team_id,
                player_id=player_id,
                passing_yards=stats.get("passing_yards", 0),
                rushing_yards=stats.get("rushing_yards", 0),
                receiving_yards=stats.get("receiving_yards", 0),
                total_yards=stats.get("total_yards", 0),
                touchdowns=stats.get("touchdowns", 0),
                receptions=stats.get("receptions", 0),
            )
            session.merge(obj)

        for player_id, stats in defense_stats.items():
            obj = PlayerStatsDefense(
                season=year,
                team_id=team_id,
                player_id=player_id,
                tackles=stats.get("tackles", 0),
                tackles_for_loss=stats.get("tackles_for_loss", 0),
                sacks=stats.get("sacks", 0),
                interceptions=stats.get("interceptions", 0),
                touchdowns=stats.get("touchdowns", 0),
            )
            session.merge(obj)

        session.commit()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Load player stats from the CFBD API into the database."
    )
    parser.add_argument(
        "--year",
        type=int,
        action="append",
        required=True,
        help="Season year to load. Provide multiple --year flags to load more than one.",
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument(
        "--team",
        help="Exact team school name as stored in the teams table (e.g., 'LSU').",
    )
    group.add_argument(
        "--all", action="store_true", help="Load stats for every team in the teams table."
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    years = args.year

    with httpx.Client(headers=HEADERS, timeout=TIMEOUT) as client:
        if args.all:
            with SessionLocal() as session:
                team_names = [team.school for team in session.query(Team).order_by(Team.school)]
            for year in years:
                for team_name in team_names:
                    print(f"[player-stats] Loading {team_name} {year}")
                    load_stats_for_team(client, year=year, team_name=team_name)
        else:
            for year in years:
                print(f"[player-stats] Loading {args.team} {year}")
                load_stats_for_team(client, year=year, team_name=args.team)


if __name__ == "__main__":
    main()
