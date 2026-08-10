"""Compute per-category returning production shares and weighted composites."""
from __future__ import annotations

import argparse
from typing import Iterable

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from db.metrics import calculate_returning_share
from db.tiers import conference_tier
from db.translation import TRANSLATION, translate
from db.models import (
    PlayerStatsDefense,
    PlayerStatsOffense,
    ReturningDetail,
    Roster,
    Team,
)
from db.session import SessionLocal
from db.weights import OFF_WEIGHTS, DEF_WEIGHTS, weighted_composite
from etl.compute_returning import _stat_total, _target_seasons

OFF_CATEGORIES = {
    "ret_passing_yards": PlayerStatsOffense.passing_yards,
    "ret_rushing_yards": PlayerStatsOffense.rushing_yards,
    "ret_receiving_yards": PlayerStatsOffense.receiving_yards,
    "ret_receptions": PlayerStatsOffense.receptions,
}
DEF_CATEGORIES = {
    "ret_tackles": PlayerStatsDefense.tackles,
    "ret_sacks": PlayerStatsDefense.sacks,
    "ret_tackles_for_loss": PlayerStatsDefense.tackles_for_loss,
    "ret_interceptions": PlayerStatsDefense.interceptions,
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Compute per-category returning production shares.",
    )
    parser.add_argument("--team", action="append",
                        help="Limit to specific team school name(s). Reuse flag for multiple teams.")
    parser.add_argument("--season", type=int, action="append",
                        help="Limit to specific season(s). Reuse flag for multiple seasons.")
    return parser.parse_args()


def _category_share(
    session: Session,
    *,
    team_id: int,
    season: int,
    table: type,
    value_column,
) -> float | None:
    """Share for one category, or None when the prior-season denominator is zero."""
    total = _stat_total(session, table, value_column, team_id=team_id, season=season - 1)
    if total <= 0:
        return None
    return calculate_returning_share(team_id, season, table, value_column, session=session)


ADJUSTED_START_SEASON = 2021  # translation coefficients are portal-era estimates

_INCOMING_SQL = """
SELECT
    o.{value_col}  AS origin_production,
    oc.conference  AS origin_conference,
    ot.school      AS origin_school
FROM rosters r
JOIN player_stats_{side} o
  ON o.player_id = r.player_id AND o.season = r.season - 1 AND o.team_id != r.team_id
JOIN teams ot ON ot.team_id = o.team_id
LEFT JOIN team_seasons oc ON oc.team_id = o.team_id AND oc.season = o.season
WHERE r.team_id = :team_id AND r.season = :season
"""


def _incoming_translated(
    session: Session, *, team_id: int, season: int, side: str, value_col: str, dest_tier: str,
) -> float:
    """Sum of incoming transfers' origin production, translated to this team's tier."""
    rows = session.execute(
        text(_INCOMING_SQL.format(side=side, value_col=value_col)),
        {"team_id": team_id, "season": season},
    ).all()
    total = 0.0
    for production, origin_conference, origin_school in rows:
        if origin_conference is None:
            continue  # non-FBS origin — no tier, no coefficient
        origin_tier = conference_tier(origin_conference, season - 1, origin_school)
        total += translate(float(production), origin_tier, dest_tier, side)
    return total


def _adjusted_metrics(
    session: Session, *, team_id: int, season: int,
    off_share: float | None, def_share: float | None,
    off_total: float, def_total: float,
) -> tuple[float | None, float | None, float | None]:
    """Continuity index including translated incoming transfers. An index — can exceed 1.0."""
    if season < ADJUSTED_START_SEASON or not TRANSLATION:
        return None, None, None

    dest_conference = session.execute(
        text("SELECT ts.conference, t.school FROM team_seasons ts "
             "JOIN teams t ON t.team_id = ts.team_id "
             "WHERE ts.team_id = :team_id AND ts.season = :season"),
        {"team_id": team_id, "season": season},
    ).first()
    if dest_conference is None:
        return None, None, None
    dest_tier = conference_tier(dest_conference[0], season, dest_conference[1])

    adjusted_off = adjusted_def = None
    if off_share is not None and off_total > 0:
        incoming = _incoming_translated(
            session, team_id=team_id, season=season,
            side="offense", value_col="total_yards", dest_tier=dest_tier)
        adjusted_off = (off_share * off_total + incoming) / off_total
    if def_share is not None and def_total > 0:
        incoming = _incoming_translated(
            session, team_id=team_id, season=season,
            side="defense", value_col="tackles", dest_tier=dest_tier)
        adjusted_def = (def_share * def_total + incoming) / def_total

    adjusted_overall = None
    if adjusted_off is not None and adjusted_def is not None and (off_total + def_total) > 0:
        adjusted_overall = (adjusted_off * off_total + adjusted_def * def_total) / (off_total + def_total)
    elif adjusted_off is not None and def_total == 0:
        adjusted_overall = adjusted_off
    elif adjusted_def is not None and off_total == 0:
        adjusted_overall = adjusted_def
    return adjusted_off, adjusted_def, adjusted_overall


def _compute_detail(session: Session, *, team_id: int, season: int) -> ReturningDetail | None:
    if season - 1 <= 0:
        return None

    shares: dict[str, float | None] = {}
    for name, column in OFF_CATEGORIES.items():
        shares[name] = _category_share(
            session, team_id=team_id, season=season,
            table=PlayerStatsOffense, value_column=column,
        )
    for name, column in DEF_CATEGORIES.items():
        shares[name] = _category_share(
            session, team_id=team_id, season=season,
            table=PlayerStatsDefense, value_column=column,
        )

    if all(v is None for v in shares.values()):
        return None

    weighted_off = weighted_composite(shares, OFF_WEIGHTS)
    weighted_def = weighted_composite(shares, DEF_WEIGHTS)

    # same production-weighted blend rule as compute_returning._compute_summary
    weighted_overall = None
    off_total = _stat_total(session, PlayerStatsOffense, PlayerStatsOffense.total_yards,
                            team_id=team_id, season=season - 1)
    def_total = _stat_total(session, PlayerStatsDefense, PlayerStatsDefense.tackles,
                            team_id=team_id, season=season - 1)
    if weighted_off is not None and weighted_def is not None and (off_total + def_total) > 0:
        weighted_overall = ((weighted_off * off_total) + (weighted_def * def_total)) / (off_total + def_total)
    elif weighted_off is not None and def_total == 0:
        weighted_overall = weighted_off
    elif weighted_def is not None and off_total == 0:
        weighted_overall = weighted_def

    off_share = _category_share(session, team_id=team_id, season=season,
                                table=PlayerStatsOffense, value_column=PlayerStatsOffense.total_yards)
    def_share = shares["ret_tackles"]
    adjusted_off, adjusted_def, adjusted_overall = _adjusted_metrics(
        session, team_id=team_id, season=season,
        off_share=off_share, def_share=def_share,
        off_total=off_total, def_total=def_total,
    )

    return ReturningDetail(
        season=season,
        team_id=team_id,
        weighted_off_pct=weighted_off,
        weighted_def_pct=weighted_def,
        weighted_overall_pct=weighted_overall,
        adjusted_off_pct=adjusted_off,
        adjusted_def_pct=adjusted_def,
        adjusted_overall_pct=adjusted_overall,
        **shares,
    )


def main() -> None:
    args = parse_args()
    run(teams=args.team, seasons=args.season)


def run(teams: Iterable[str] | None = None, seasons: Iterable[int] | None = None) -> None:
    allowed_teams = set(teams) if teams else None
    allowed_seasons = set(seasons) if seasons else None

    with SessionLocal() as session:
        team_query = select(Team.team_id, Team.school).order_by(Team.school)
        if allowed_teams is not None:
            team_query = team_query.where(Team.school.in_(allowed_teams))
        team_rows = session.execute(team_query).all()

        for team_id, team_name in team_rows:
            roster_seasons = set(
                session.execute(
                    select(Roster.season).where(Roster.team_id == team_id).distinct()
                ).scalars()
            )
            if not roster_seasons:
                continue

            for season in _target_seasons(roster_seasons, allowed_seasons):
                if (season - 1) not in roster_seasons:
                    continue

                detail = _compute_detail(session, team_id=team_id, season=season)
                if detail is None:
                    continue

                session.merge(detail)
                overall = detail.weighted_overall_pct
                weighted = f"{overall:.3f}" if overall is not None else "n/a"
                print(f"[detail] {team_name} {season}: weighted={weighted}")

        session.commit()


if __name__ == "__main__":
    main()
