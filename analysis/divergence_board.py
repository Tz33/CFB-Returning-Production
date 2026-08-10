# analysis/divergence_board.py
"""The portal divergence board: teams the consensus most misvalues.

Published returning-production numbers (what markets and Connelly-derived
models anchor on) measure raw retention. The portal-adjusted continuity index
credits incoming transfers at translated value. Where the two diverge most is
where consensus win totals should be systematically wrong — backtested at
60.0% against market totals on this subset vs 51.2% for a raw-returning model
(2022-2025 folds, n=80).

Market column degrades gracefully: win_totals rows for the season if loaded,
else a count of posted game spreads, else '—'.
"""
import argparse

import pandas as pd
from sqlalchemy import text

from db.session import engine

BOARD_SQL = """
SELECT
    t.school,
    ts.conference,
    rs.overall_pct                   AS raw_retention,
    rd.adjusted_overall_pct          AS portal_adjusted,
    rd.adjusted_overall_pct - rs.overall_pct AS gap,
    wp.rating_pred,
    wp.expected_wins,
    wt.win_total                     AS market_total,
    (SELECT COUNT(*) FROM game_lines gl
      WHERE gl.season = rs.season
        AND (gl.home_team_id = rs.team_id OR gl.away_team_id = rs.team_id)
        AND gl.spread IS NOT NULL)   AS posted_spreads
FROM returning_summary rs
JOIN teams t ON t.team_id = rs.team_id
JOIN returning_detail rd ON rd.team_id = rs.team_id AND rd.season = rs.season
LEFT JOIN team_seasons ts ON ts.team_id = rs.team_id AND ts.season = rs.season
LEFT JOIN win_projections wp ON wp.team_id = rs.team_id AND wp.season = rs.season
LEFT JOIN win_totals wt ON wt.team_id = rs.team_id AND wt.season = rs.season
WHERE rs.season = :season AND rd.adjusted_overall_pct IS NOT NULL
"""


def build_board(season: int) -> pd.DataFrame:
    df = pd.read_sql(text(BOARD_SQL), engine, params={"season": season})
    df["lean"] = df.apply(
        lambda r: ("OVER" if r["expected_wins"] > r["market_total"] else "UNDER")
        if pd.notna(r["market_total"]) and pd.notna(r["expected_wins"]) else None, axis=1)
    df["market"] = df.apply(
        lambda r: f"{r['market_total']:.1f}" if pd.notna(r["market_total"])
        else (f"({int(r['posted_spreads'])} spreads posted)" if r["posted_spreads"] else "—"),
        axis=1)
    return df


def print_board(df: pd.DataFrame, title: str) -> None:
    view = df[["school", "conference", "raw_retention", "portal_adjusted", "gap",
               "rating_pred", "expected_wins", "market", "lean"]].copy()
    for col in ("raw_retention", "portal_adjusted", "gap", "rating_pred", "expected_wins"):
        view[col] = view[col].astype(float).round(3)
    view["lean"] = view["lean"].fillna("n/a")
    print(f"\n=== {title} ===")
    print(view.to_string(index=False))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--season", type=int, default=2026)
    parser.add_argument("--top", type=int, default=15)
    args = parser.parse_args()

    df = build_board(args.season)
    print(f"Portal divergence board, {args.season} — {len(df)} teams")
    print("Backtested on the top-divergence quintile 2022-2025: model 60.0% vs market "
          "(n=80, p=.09), raw-returning baseline 51.2% on identical teams. "
          "Rerun analysis/backtest_win_projections.py to refresh.")

    print_board(df.nlargest(args.top, "gap"),
                "Portal-UNDERRATED (consensus sees less production returning than reality)")
    # the gap is one-sided by construction (incoming production only adds), so the
    # complementary view is the true continuity bottom: lost production, didn't reload
    print_board(df.nsmallest(args.top, "portal_adjusted"),
                "Production-DEPLETED (lowest adjusted continuity: heavy losses, no portal reload)")


if __name__ == "__main__":
    main()
