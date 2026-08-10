# analysis/validate_market_spreads.py
"""Does returning production predict early-season point-spread errors?

If markets underprice roster continuity in weeks 1-4 (when they have the
least game data), the returning-production differential between two teams
should correlate with the home team's cover margin early but not late
(weeks 8+, by when the market has absorbed actual play). Expected effects
are small (|r| < 0.1); a null result means the market prices it — that is a
legitimate finding.
"""
import argparse

import pandas as pd
from scipy import stats
from sqlalchemy import text

from db.session import engine

DATASET_SQL = """
SELECT
    g.season, g.week, g.spread, g.home_score, g.away_score,
    hr.overall_pct  AS home_ret, ar.overall_pct  AS away_ret,
    hd.weighted_overall_pct AS home_wret, ad.weighted_overall_pct AS away_wret,
    hd.adjusted_overall_pct AS home_aret, ad.adjusted_overall_pct AS away_aret
FROM game_lines g
JOIN returning_summary hr ON hr.team_id = g.home_team_id AND hr.season = g.season
JOIN returning_summary ar ON ar.team_id = g.away_team_id AND ar.season = g.season
LEFT JOIN returning_detail hd ON hd.team_id = g.home_team_id AND hd.season = g.season
LEFT JOIN returning_detail ad ON ad.team_id = g.away_team_id AND ad.season = g.season
WHERE g.season BETWEEN :start AND :end
  AND g.season_type = 'regular'
  AND g.home_team_id IS NOT NULL AND g.away_team_id IS NOT NULL
  AND g.home_score IS NOT NULL AND g.away_score IS NOT NULL
  AND g.spread IS NOT NULL
"""

METRICS = [("ret_diff", "home_ret", "away_ret"),
           ("wret_diff", "home_wret", "away_wret"),
           ("aret_diff", "home_aret", "away_aret")]


def cover_margin(home_score: int, away_score: int, spread: float) -> float:
    """Positive = home covered; spread is home-relative (negative = home favored)."""
    return (home_score - away_score) + spread


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--start-season", type=int, default=2015)
    parser.add_argument("--end-season", type=int, default=2025)
    args = parser.parse_args()

    df = pd.read_sql(text(DATASET_SQL), engine,
                     params={"start": args.start_season, "end": args.end_season})
    df = df[~df["season"].isin([2020, 2021])]
    df["home_margin"] = df["home_score"] - df["away_score"]
    df["cover_margin"] = df.apply(
        lambda r: cover_margin(r["home_score"], r["away_score"], r["spread"]), axis=1)
    for name, home, away in METRICS:
        df[name] = df[home] - df[away]

    print(f"n={len(df)} FBS-vs-FBS regular-season games with spreads, "
          f"seasons {df['season'].min()}-{df['season'].max()} (COVID seasons dropped)")

    # sanity gate: spreads must strongly predict margins or the sign convention is wrong
    sanity = df["spread"].corr(df["home_margin"])
    print(f"\nsanity gate: r(spread, home_margin) = {sanity:.3f} (expect ~ -0.7)")
    if sanity > -0.5:
        raise SystemExit("ABORT: spread sign convention looks wrong — check the loader")
    print(df[["season", "week", "spread", "home_margin", "cover_margin"]].head(5).to_string(index=False))

    print("\nTest 1 — r(returning diff, cover margin), early vs late season:")
    early = df[df["week"] <= 4]
    late = df[df["week"] >= 8]
    for name, _, _ in METRICS:
        e = early[[name, "cover_margin"]].dropna()
        l = late[[name, "cover_margin"]].dropna()
        r_e = e[name].corr(e["cover_margin"]) if len(e) > 50 else float("nan")
        r_l = l[name].corr(l["cover_margin"]) if len(l) > 50 else float("nan")
        p_e = stats.pearsonr(e[name], e["cover_margin"]).pvalue if len(e) > 50 else float("nan")
        print(f"  {name:>10}: weeks 1-4 r={r_e:.3f} (n={len(e)}, p={p_e:.3f}) | "
              f"weeks 8+ r={r_l:.3f} (n={len(l)})")

    print("\nTest 2 — home cover rate by returning-diff quintile (weeks 1-4, pushes excluded):")
    sub = early[early["cover_margin"] != 0].dropna(subset=["ret_diff"]).copy()
    sub["quintile"] = pd.qcut(sub["ret_diff"], 5, labels=["Q1 (away adv)", "Q2", "Q3", "Q4", "Q5 (home adv)"])
    table = sub.groupby("quintile", observed=True).agg(
        n=("cover_margin", "size"),
        home_cover_rate=("cover_margin", lambda s: (s > 0).mean()),
    ).round(3)
    print(table.to_string())

    top = sub[sub["quintile"] == "Q5 (home adv)"]
    bottom = sub[sub["quintile"] == "Q1 (away adv)"]
    contrast = pd.concat([top.assign(pick_cover=top["cover_margin"] > 0),
                          bottom.assign(pick_cover=bottom["cover_margin"] < 0)])
    wins = int(contrast["pick_cover"].sum())
    n = len(contrast)
    test = stats.binomtest(wins, n, 0.5)
    print(f"\n'bet the returning-production side' in extreme quintiles: "
          f"{wins}/{n} = {wins/n:.3f} (binomial p={test.pvalue:.3f} vs 0.5)")


if __name__ == "__main__":
    main()
