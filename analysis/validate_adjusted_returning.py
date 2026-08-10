# analysis/validate_adjusted_returning.py
"""Does crediting translated transfer production improve prediction?

Head-to-head on identical rows: adjusted continuity index vs the unadjusted
returning share vs the weighted composite, against delta SP+. Eval window
defaults to 2022-2025 — the portal starts in 2021 but that season is a COVID
pair. At n~530, r differences under ~0.05 are noise; effect size and
direction are the deliverable.
"""
import argparse
import math

import numpy as np
import pandas as pd
from scipy import stats
from sqlalchemy import text

from db.session import engine
from analysis.validate_weighted_returning import steiger_z

DATASET_SQL = """
SELECT
    d.season, t.school,
    rs.overall_pct, rs.off_pct,
    d.weighted_overall_pct,
    d.adjusted_off_pct, d.adjusted_def_pct, d.adjusted_overall_pct,
    cur.wins - prev.wins AS delta_wins,
    cur.sp_rating - prev.sp_rating AS delta_sp
FROM returning_detail d
JOIN returning_summary rs ON rs.team_id = d.team_id AND rs.season = d.season
JOIN teams t ON t.team_id = d.team_id
JOIN team_outcomes cur  ON cur.team_id = d.team_id AND cur.season = d.season
JOIN team_outcomes prev ON prev.team_id = d.team_id AND prev.season = d.season - 1
WHERE d.season BETWEEN :start AND :end
  AND d.adjusted_overall_pct IS NOT NULL
"""

PAIRS = [
    ("adjusted_overall_pct", "overall_pct"),
    ("adjusted_off_pct", "off_pct"),
    ("adjusted_overall_pct", "weighted_overall_pct"),
]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--start-season", type=int, default=2022)
    parser.add_argument("--end-season", type=int, default=2025)
    args = parser.parse_args()

    df = pd.read_sql(text(DATASET_SQL), engine,
                     params={"start": args.start_season, "end": args.end_season})
    df = df[(df["overall_pct"] >= 0) & (df["overall_pct"] <= 1)]
    print(f"n={len(df)}, seasons {df['season'].min()}-{df['season'].max()}")
    print(f"adjusted index range: {df['adjusted_overall_pct'].min():.3f} "
          f"to {df['adjusted_overall_pct'].max():.3f} "
          f"({int((df['adjusted_overall_pct'] > 1).sum())} team-seasons above 1.0)")

    print("\nCorrelations vs delta_sp (identical rows):")
    predictors = ["overall_pct", "off_pct", "weighted_overall_pct",
                  "adjusted_overall_pct", "adjusted_off_pct", "adjusted_def_pct"]
    for p in predictors:
        sub = df[[p, "delta_sp"]].dropna()
        print(f"  {p:>22}: r={sub[p].corr(sub['delta_sp']):.3f} (n={len(sub)})")

    print("\nSteiger's z head-to-heads (outcome delta_sp):")
    for new, old in PAIRS:
        shared = df[[new, old, "delta_sp"]].dropna()
        r_new = shared["delta_sp"].corr(shared[new])
        r_old = shared["delta_sp"].corr(shared[old])
        r_between = shared[new].corr(shared[old])
        z, p = steiger_z(r_new, r_old, r_between, len(shared))
        better = new if r_new > r_old else old
        print(f"  {new} vs {old}: r={r_new:.3f} vs {r_old:.3f} "
              f"(z={z:.2f}, p={p:.3f}) -> {better}")

    print("\nBuckets on adjusted_overall_pct:")
    edges = [0, 0.5, 0.75, 1.0, float("inf")]
    labels = ["<50%", "50-75%", "75-100%", "100%+"]
    bucketed = df.assign(bucket=pd.cut(df["adjusted_overall_pct"], edges, labels=labels))
    print(bucketed.groupby("bucket", observed=True)
          .agg(n=("bucket", "size"),
               mean_delta_wins=("delta_wins", "mean"),
               mean_delta_sp=("delta_sp", "mean"))
          .round(3).to_string())

    print("\nCaveat: at this sample size, r differences under ~0.05 are within noise; "
          "direction and consistency across offense/overall are the meaningful signal.")


if __name__ == "__main__":
    main()
