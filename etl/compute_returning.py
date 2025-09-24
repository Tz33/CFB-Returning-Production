"""Compute returning production summaries and persist them to the database."""
from __future__ import annotations

import argparse
from typing import Iterable

from sqlalchemy import func, select
from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import InstrumentedAttribute

from db.metrics import calculate_returning_share
from db.models import (
    PlayerStatsDefense,
    PlayerStatsOffense,
    ReturningSummary,
    Roster,
    Team,
)
from db.session import SessionLocal


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Compute returning production percentages for teams and seasons.",
    )
    parser.add_argument(
        "--team",
        action="append",
        help="Limit computation to specific team school name(s). Reuse flag for multiple teams.",
    )
    parser.add_argument(
        "--season",
        type=int,
        action="append",
        help="Limit computation to specific season(s). Reuse flag for multiple seasons.",
    )
    return parser.parse_args()


def _stat_total(
    session: Session,
    table: type[PlayerStatsOffense] | type[PlayerStatsDefense],
    value_column: InstrumentedAttribute[float | int],
    *,
    team_id: int,
    season: int,
) -> float:
    result = session.execute(
        select(func.coalesce(func.sum(value_column), 0)).where(
            table.team_id == team_id,
            table.season == season,
        )
    ).scalar_one()
    return float(result or 0)


def _target_seasons(
    all_seasons: Iterable[int],
    allowed_seasons: set[int] | None,
) -> list[int]:
    seasons = list(all_seasons)
    if allowed_seasons is not None:
        seasons = [season for season in seasons if season in allowed_seasons]
    return sorted(seasons)


def _compute_summary(
    session: Session,
    *,
    team_id: int,
    season: int,
) -> ReturningSummary | None:
    previous_season = season - 1
    if previous_season <= 0:
        return None

    offense_pct = calculate_returning_share(
        team_id,
        season,
        PlayerStatsOffense,
        PlayerStatsOffense.total_yards,
        session=session,
    )
    defense_pct = calculate_returning_share(
        team_id,
        season,
        PlayerStatsDefense,
        PlayerStatsDefense.tackles,
        session=session,
    )

    offense_total = _stat_total(
        session,
        PlayerStatsOffense,
        PlayerStatsOffense.total_yards,
        team_id=team_id,
        season=previous_season,
    )
    defense_total = _stat_total(
        session,
        PlayerStatsDefense,
        PlayerStatsDefense.tackles,
        team_id=team_id,
        season=previous_season,
    )

    combined_total = offense_total + defense_total
    if combined_total > 0:
        overall_pct = (
            (offense_pct * offense_total) + (defense_pct * defense_total)
        ) / combined_total
    elif offense_total > 0:
        overall_pct = offense_pct
    elif defense_total > 0:
        overall_pct = defense_pct
    else:
        return None

    return ReturningSummary(
        season=season,
        team_id=team_id,
        off_pct=offense_pct,
        def_pct=defense_pct,
        overall_pct=overall_pct,
    )


def main() -> None:
    args = parse_args()
    allowed_teams = set(args.team) if args.team else None
    allowed_seasons = set(args.season) if args.season else None

    with SessionLocal() as session:
        team_query = select(Team.team_id, Team.school).order_by(Team.school)
        if allowed_teams is not None:
            team_query = team_query.where(Team.school.in_(allowed_teams))
        teams = session.execute(team_query).all()

        for team_id, team_name in teams:
            roster_seasons_all = set(
                session.execute(
                    select(Roster.season)
                    .where(Roster.team_id == team_id)
                    .distinct()
                ).scalars()
            )
            if not roster_seasons_all:
                continue

            seasons_to_process = _target_seasons(
                roster_seasons_all,
                allowed_seasons,
            )

            for season in seasons_to_process:
                if (season - 1) not in roster_seasons_all:
                    continue

                summary = _compute_summary(session, team_id=team_id, season=season)
                if summary is None:
                    continue

                session.merge(summary)
                print(
                    f"[returning] {team_name} {season}: "
                    f"off={summary.off_pct:.3f} def={summary.def_pct:.3f} "
                    f"overall={summary.overall_pct:.3f}"
                )

        session.commit()


if __name__ == "__main__":
    main()
