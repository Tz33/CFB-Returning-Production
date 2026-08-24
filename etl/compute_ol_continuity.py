# etl/compute_ol_continuity.py
"""Compute returning offensive-line starts share onto returning_detail.

ret_ol_starts_share = (prior-season games started by OL who appear on this
season's CFBD roster) / (all prior-season OL games started). Starts come from
player_participation (NCAA GP/GS); "returning" is a normalized-name match
against the CFBD roster, since the sources share no player ids. NULL when the
prior season has no recorded OL starts.
"""
from __future__ import annotations

import argparse
from typing import Iterable

from sqlalchemy import select
from sqlalchemy.orm import Session

from db.names import normalize_player_name
from db.models import PlayerParticipation, ReturningDetail, Roster, Team
from db.session import SessionLocal

OL_POSITIONS = {"OL", "OT", "OG", "OC", "C", "G", "T"}


def ol_starts_share(
    prior_ol_rows: Iterable[tuple[str, int]],
    roster_names: set[str],
) -> tuple[float | None, int, int]:
    """(share, returning_starts, total_starts) from (name, gs) rows and the
    normalized-name set of the current roster."""
    total = returning = 0
    for name, starts in prior_ol_rows:
        total += starts
        if starts and normalize_player_name(name) in roster_names:
            returning += starts
    if total <= 0:
        return None, returning, total
    return returning / total, returning, total


def _compute_team_season(session: Session, *, team_id: int, season: int) -> float | None:
    prior_rows = session.execute(
        select(PlayerParticipation.player_name, PlayerParticipation.games_started)
        .where(
            PlayerParticipation.team_id == team_id,
            PlayerParticipation.season == season - 1,
            PlayerParticipation.position.in_(OL_POSITIONS),
        )
    ).all()
    if not prior_rows:
        return None

    roster_names = {
        normalize_player_name(name)
        for name in session.execute(
            select(Roster.full_name).where(
                Roster.team_id == team_id, Roster.season == season)
        ).scalars()
    }
    if not roster_names:
        return None

    share, _, _ = ol_starts_share([(n, gs) for n, gs in prior_rows], roster_names)
    return share


def run(teams: Iterable[str] | None = None, seasons: Iterable[int] | None = None) -> None:
    allowed_teams = set(teams) if teams else None
    allowed_seasons = set(seasons) if seasons else None

    with SessionLocal() as session:
        team_query = select(Team.team_id, Team.school).order_by(Team.school)
        if allowed_teams is not None:
            team_query = team_query.where(Team.school.in_(allowed_teams))

        for team_id, team_name in session.execute(team_query).all():
            participation_seasons = set(
                session.execute(
                    select(PlayerParticipation.season)
                    .where(PlayerParticipation.team_id == team_id).distinct()
                ).scalars()
            )
            target_seasons = {s + 1 for s in participation_seasons}
            if allowed_seasons is not None:
                target_seasons &= allowed_seasons

            for season in sorted(target_seasons):
                share = _compute_team_season(session, team_id=team_id, season=season)
                if share is None:
                    continue
                detail = session.get(ReturningDetail, (season, team_id))
                if detail is None:
                    detail = ReturningDetail(season=season, team_id=team_id)
                    session.add(detail)
                detail.ret_ol_starts_share = share
                print(f"[ol] {team_name} {season}: ret_ol_starts_share={share:.3f}")

        session.commit()


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Compute returning OL starts share onto returning_detail.")
    parser.add_argument("--team", action="append",
                        help="Limit to specific team school name(s). Reuse flag for multiple teams.")
    parser.add_argument("--season", type=int, action="append",
                        help="Limit to specific season(s). Reuse flag for multiple seasons.")
    args = parser.parse_args()
    run(teams=args.team, seasons=args.season)


if __name__ == "__main__":
    main()
