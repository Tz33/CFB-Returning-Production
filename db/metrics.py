"""Utility functions for calculating team production metrics."""

from __future__ import annotations

from typing import Any

from sqlalchemy import and_, column, func, select, table
from sqlalchemy.orm import Session, aliased
from sqlalchemy.orm.attributes import InstrumentedAttribute
from sqlalchemy.sql import Select

from db.models import PlayerStatsOffense, Roster
from db.session import SessionLocal


_mv_incoming = table(
    "mv_incoming",
    column("season"),
    column("team_id"),
    column("player_id"),
)


def _returning_player_ids_query(team_id: int, season: int, prev_season: int) -> Select[tuple[int]]:
    """Build a query that returns player IDs on the roster in *season* and *prev_season*."""

    current_roster = aliased(Roster)
    previous_roster = aliased(Roster)

    return (
        select(current_roster.player_id)
        .join(
            previous_roster,
            and_(
                previous_roster.player_id == current_roster.player_id,
                previous_roster.team_id == current_roster.team_id,
                previous_roster.season == prev_season,
            ),
        )
        .where(
            current_roster.team_id == team_id,
            current_roster.season == season,
        )
        .distinct()
    )


def _calculate_returning_share(
    session: Session,
    team_id: int,
    season: int,
    table: type,
    value_column: InstrumentedAttribute[Any],
) -> float:
    """Return the fraction of prior-season production attributable to returning players."""

    previous_season = season - 1
    if previous_season <= 0:
        return 0.0

    total_stmt = select(func.coalesce(func.sum(value_column), 0)).where(
        table.team_id == team_id,
        table.season == previous_season,
    )
    total_value = session.execute(total_stmt).scalar_one()
    if not total_value:
        return 0.0

    returning_players = _returning_player_ids_query(
        team_id, season, previous_season
    ).subquery()

    returning_stmt = select(func.coalesce(func.sum(value_column), 0)).where(
        table.team_id == team_id,
        table.season == previous_season,
        table.player_id.in_(select(returning_players.c.player_id)),
    )
    returning_value = session.execute(returning_stmt).scalar_one()

    return float(returning_value) / float(total_value)


def calculate_returning_share(
    team_id: int,
    season: int,
    table: type,
    value_column: InstrumentedAttribute[Any],
    *,
    session: Session | None = None,
) -> float:
    """Return the share of prior-season production for *table* accounted for by returners."""

    manage_session = False
    if session is None:
        session = SessionLocal()
        manage_session = True

    try:
        return _calculate_returning_share(session, team_id, season, table, value_column)
    finally:
        if manage_session:
            session.close()


def calculate_returning_percentage(team_id: int, season: int) -> float:
    """Return the share of offensive yards from the prior season produced by returning players."""

    return calculate_returning_share(
        team_id,
        season,
        PlayerStatsOffense,
        PlayerStatsOffense.total_yards,
    )


def classify_incoming(
    team_id: int,
    season: int,
    *,
    session: Session | None = None,
) -> dict[str, int]:
    """Return counts of incoming players split between transfers and freshmen."""

    manage_session = False
    if session is None:
        session = SessionLocal()
        manage_session = True

    try:
        incoming_players = (
            select(_mv_incoming.c.player_id)
            .where(
                _mv_incoming.c.team_id == team_id,
                _mv_incoming.c.season == season,
            )
            .subquery()
        )

        total_incoming = int(
            session.execute(
                select(func.count()).select_from(incoming_players)
            ).scalar_one()
        )

        if total_incoming == 0:
            return {"transfers": 0, "freshmen": 0}

        previous_season = season - 1
        if previous_season <= 0:
            return {"transfers": 0, "freshmen": total_incoming}

        transfer_count = int(
            session.execute(
                select(func.count(func.distinct(incoming_players.c.player_id)))
                .select_from(
                    incoming_players.join(
                        Roster,
                        and_(
                            Roster.player_id == incoming_players.c.player_id,
                            Roster.season == previous_season,
                            Roster.team_id != team_id,
                        ),
                    )
                )
            ).scalar_one()
        )

        freshmen_count = total_incoming - transfer_count
        if freshmen_count < 0:
            freshmen_count = 0

        return {"transfers": transfer_count, "freshmen": freshmen_count}
    finally:
        if manage_session:
            session.close()

