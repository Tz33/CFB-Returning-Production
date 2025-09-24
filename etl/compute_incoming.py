"""Compute incoming player summaries and persist them to the database."""
from __future__ import annotations

import argparse
from typing import Iterable

from sqlalchemy import select
from sqlalchemy.orm import Session

from db.metrics import classify_incoming
from db.models import IncomingSummary, Roster, Team
from db.session import SessionLocal


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments."""

    parser = argparse.ArgumentParser(
        description="Compute incoming player mix for teams and seasons.",
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
) -> tuple[IncomingSummary, int, int, int]:
    counts = classify_incoming(team_id, season, session=session)
    transfers = int(counts.get("transfers", 0))
    freshmen = int(counts.get("freshmen", 0))
    total_incoming = transfers + freshmen
    if total_incoming > 0:
        transfer_share = transfers / total_incoming
    else:
        transfer_share = 0.0

    summary = IncomingSummary(
        season=season,
        team_id=team_id,
        transfer_share=transfer_share,
        freshman_count=freshmen,
    )
    return summary, transfers, freshmen, total_incoming


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
            roster_seasons = set(
                session.execute(
                    select(Roster.season)
                    .where(Roster.team_id == team_id)
                    .distinct()
                ).scalars()
            )
            if not roster_seasons:
                continue

            seasons_to_process = _target_seasons(roster_seasons, allowed_seasons)

            for season in seasons_to_process:
                summary, transfers, freshmen, total_incoming = _compute_summary(
                    session,
                    team_id=team_id,
                    season=season,
                )

                session.merge(summary)
                print(
                    f"[incoming] {team_name} {season}: "
                    f"transfers={transfers} freshmen={freshmen} "
                    f"total={total_incoming} share={summary.transfer_share:.3f}"
                )

        session.commit()

if __name__ == "__main__":
    main()
