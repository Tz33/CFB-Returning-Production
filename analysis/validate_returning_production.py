# analysis/validate_returning_production.py
"""Measure how returning production correlates with next-season team success.

Joins returning_summary (season Y) with team_outcomes at Y and Y-1, then
reports correlations, OLS slopes, and bucket summaries for the deltas in
win percentage, wins, and SP+ rating.
"""
import argparse
import os

import numpy as np
import pandas as pd
from sqlalchemy import text

from db.session import engine

PREDICTORS = ["overall_pct", "off_pct", "def_pct"]
OUTCOMES = ["delta_win_pct", "delta_wins", "delta_sp"]
BUCKET_EDGES = [0, 0.4, 0.6, 0.8, 1.0001]
BUCKET_LABELS = ["<40%", "40-60%", "60-80%", "80%+"]

DATASET_SQL = """
SELECT
    r.season,
    t.school,
    r.off_pct,
    r.def_pct,
    r.overall_pct,
    cur.wins,
    cur.win_pct,
    cur.sp_rating,
    prev.wins      AS wins_prev,
    prev.win_pct   AS win_pct_prev,
    prev.sp_rating AS sp_rating_prev
FROM returning_summary r
JOIN teams t ON t.team_id = r.team_id
JOIN team_outcomes cur  ON cur.team_id = r.team_id AND cur.season = r.season
JOIN team_outcomes prev ON prev.team_id = r.team_id AND prev.season = r.season - 1
WHERE r.season BETWEEN :start AND :end
"""

def load_dataset(start_season: int, end_season: int) -> pd.DataFrame:
    df = pd.read_sql(text(DATASET_SQL), engine, params={"start": start_season, "end": end_season})

    degenerate = (df["overall_pct"] == 0) & (df["off_pct"] == 0) & (df["def_pct"] == 0)
    if degenerate.any():
        print(f"dropped {int(degenerate.sum())} degenerate all-zero rows")
        df = df[~degenerate]

    # tiny denominators (FCS-era rows for teams that later joined FBS) can push shares out of range
    out_of_range = (df[PREDICTORS].lt(0) | df[PREDICTORS].gt(1)).any(axis=1)
    if out_of_range.any():
        print(f"dropped {int(out_of_range.sum())} rows with shares outside [0,1]")
        df = df[~out_of_range]

    df = df.copy()
    df["delta_wins"] = df["wins"] - df["wins_prev"]
    df["delta_win_pct"] = df["win_pct"] - df["win_pct_prev"]
    df["delta_sp"] = df["sp_rating"] - df["sp_rating_prev"]
    # both the 2019->2020 and 2020->2021 pairs involve the shortened COVID season
    df["covid_flag"] = df["season"].isin([2020, 2021])
    return df

def compute_correlations(df: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for x in PREDICTORS:
        for y in OUTCOMES:
            sub = df[[x, y]].dropna()
            slope, intercept = np.polyfit(sub[x], sub[y], 1)
            rows.append({
                "predictor": x,
                "outcome": y,
                "n": len(sub),
                "pearson_r": sub[x].corr(sub[y]),
                "spearman_r": sub[x].corr(sub[y], method="spearman"),
                "ols_slope": slope,
            })
    return pd.DataFrame(rows)

def bucket_summary(df: pd.DataFrame, col: str = "overall_pct") -> pd.DataFrame:
    bucketed = df.assign(bucket=pd.cut(df[col], BUCKET_EDGES, labels=BUCKET_LABELS))
    return (
        bucketed.groupby("bucket", observed=True)
        .agg(
            n=("bucket", "size"),
            mean_delta_wins=("delta_wins", "mean"),
            median_delta_wins=("delta_wins", "median"),
            mean_delta_win_pct=("delta_win_pct", "mean"),
            mean_delta_sp=("delta_sp", "mean"),
        )
        .round(3)
    )

def report(df: pd.DataFrame, label: str) -> None:
    print(f"\n=== {label} (n={len(df)}, seasons {df['season'].min()}-{df['season'].max()}) ===")
    print("\nCorrelations (positive = more returning production, bigger improvement):")
    print(compute_correlations(df).round(3).to_string(index=False))
    print("\nBy overall returning-production bucket:")
    buckets = bucket_summary(df)
    print(buckets.to_string())

    top = buckets.loc["80%+"] if "80%+" in buckets.index else None
    if top is not None:
        print(f"\nHeadline: teams returning 80%+ of production averaged "
              f"{top['mean_delta_wins']:+.2f} wins and {top['mean_delta_sp']:+.2f} SP+ "
              f"vs the prior season (n={int(top['n'])}).")

def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--start-season", type=int, default=2015)
    parser.add_argument("--end-season", type=int, default=2025)
    parser.add_argument("--include-covid", action="store_true",
                        help="Keep the 2020/2021 COVID-distorted pairs in the analysis")
    parser.add_argument("--out", default=os.path.join("analysis", "output", "returning_production_merged.csv"))
    args = parser.parse_args()

    df = load_dataset(args.start_season, args.end_season)

    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    df.to_csv(args.out, index=False)
    print(f"merged dataset written to {args.out}")

    if args.include_covid:
        report(df, "All seasons (COVID pairs included)")
    else:
        excluded = int(df["covid_flag"].sum())
        print(f"excluding {excluded} COVID-distorted rows (2020/2021 seasons); "
              f"use --include-covid to keep them")
        report(df[~df["covid_flag"]], "COVID pairs excluded")


if __name__ == "__main__":
    main()
