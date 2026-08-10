# analysis/validate_win_totals.py
"""Benchmark a returning-production win model against market preseason totals.

Leakage-free by construction: the naive model (delta_wins ~ returning pct) is
fit ONLY on 2015-2018 and never refit on evaluation seasons. For each
market total: lean = sign(model wins - total); a hit = the actual result
landed on the leaned side. Pushes excluded. Near coin-flip is the expected
outcome — the market is strong — and still a publishable validation.
"""
import argparse

import numpy as np
import pandas as pd
from scipy import stats
from sqlalchemy import text

from db.session import engine

FIT_SEASONS = (2015, 2018)

FIT_SQL = """
SELECT rs.overall_pct,
       cur.wins - prev.wins AS delta_wins
FROM returning_summary rs
JOIN team_outcomes cur  ON cur.team_id = rs.team_id AND cur.season = rs.season
JOIN team_outcomes prev ON prev.team_id = rs.team_id AND prev.season = rs.season - 1
WHERE rs.season BETWEEN :fit_start AND :fit_end
  AND rs.overall_pct BETWEEN 0 AND 1
"""

EVAL_SQL = """
SELECT
    wt.season, t.school, wt.win_total,
    rs.overall_pct,
    d.weighted_overall_pct,
    d.adjusted_overall_pct,
    cur.wins   AS actual_wins,
    cur.wins + cur.losses AS games,
    prev.wins  AS prior_wins
FROM win_totals wt
JOIN teams t ON t.team_id = wt.team_id
JOIN returning_summary rs ON rs.team_id = wt.team_id AND rs.season = wt.season
LEFT JOIN returning_detail d ON d.team_id = wt.team_id AND d.season = wt.season
JOIN team_outcomes cur  ON cur.team_id = wt.team_id AND cur.season = wt.season
JOIN team_outcomes prev ON prev.team_id = wt.team_id AND prev.season = wt.season - 1
WHERE wt.season NOT IN (2020, 2021)
"""


def evaluate(df: pd.DataFrame, predictor: str, a: float, b: float) -> None:
    sub = df.dropna(subset=[predictor]).copy()
    sub["model_wins"] = (sub["prior_wins"] + a + b * sub[predictor]).clip(0, sub["games"])
    sub["lean"] = np.sign(sub["model_wins"] - sub["win_total"])
    sub["result"] = np.sign(sub["actual_wins"] - sub["win_total"])
    sub = sub[(sub["lean"] != 0) & (sub["result"] != 0)]  # drop no-lean rows and pushes
    sub["hit"] = sub["lean"] == sub["result"]

    n, wins = len(sub), int(sub["hit"].sum())
    if n == 0:
        print(f"  {predictor}: no evaluable rows")
        return
    p = stats.binomtest(wins, n, 0.5).pvalue
    print(f"\n  {predictor}: {wins}/{n} = {wins/n:.3f} (binomial p={p:.3f})")

    for magnitude in (1.0, 2.0):
        strong = sub[(sub["model_wins"] - sub["win_total"]).abs() >= magnitude]
        if len(strong) >= 10:
            w = int(strong["hit"].sum())
            print(f"    leans >= {magnitude:.0f} wins: {w}/{len(strong)} = {w/len(strong):.3f}")

    per_season = sub.groupby("season")["hit"].agg(["sum", "size"])
    per_season["rate"] = (per_season["sum"] / per_season["size"]).round(3)
    print(per_season.rename(columns={"sum": "hits", "size": "n"}).to_string())


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.parse_args()

    fit = pd.read_sql(text(FIT_SQL), engine,
                      params={"fit_start": FIT_SEASONS[0], "fit_end": FIT_SEASONS[1]})
    b, a = np.polyfit(fit["overall_pct"], fit["delta_wins"], 1)
    print(f"naive model fit on {FIT_SEASONS[0]}-{FIT_SEASONS[1]} (n={len(fit)}): "
          f"model_wins = prior_wins + {a:.2f} + {b:.2f} * returning_pct")

    df = pd.read_sql(text(EVAL_SQL), engine)
    if df.empty:
        raise SystemExit("no win totals loaded — fill data/win_totals.csv and run "
                         "python -m etl.load_win_totals")
    print(f"eval: n={len(df)} team-seasons with market totals, "
          f"seasons {sorted(df['season'].unique())} (COVID excluded)")

    for predictor in ["overall_pct", "weighted_overall_pct", "adjusted_overall_pct"]:
        evaluate(df, predictor, a, b)


if __name__ == "__main__":
    main()
