# analysis/validate_weighted_returning.py
"""Head-to-head: weighted per-category composite vs the baseline overall_pct.

Scores every predictor on the identical row set so correlations are directly
comparable, and tests the weighted-vs-baseline difference with Steiger's z
for dependent correlations.
"""
import argparse
import math

import numpy as np
import pandas as pd
from scipy import stats
from sqlalchemy import text

from db.session import engine

PREDICTORS = [
    "overall_pct", "off_pct", "def_pct",
    "weighted_overall_pct", "weighted_off_pct", "weighted_def_pct",
    "ret_passing_yards", "ret_rushing_yards", "ret_receiving_yards", "ret_receptions",
    "ret_tackles", "ret_sacks", "ret_tackles_for_loss", "ret_interceptions",
]
OUTCOMES = ["delta_win_pct", "delta_wins", "delta_sp"]
BUCKET_EDGES = [0, 0.4, 0.6, 0.8, 1.0001]
BUCKET_LABELS = ["<40%", "40-60%", "60-80%", "80%+"]

DATASET_SQL = """
SELECT
    d.season, t.school,
    rs.off_pct, rs.def_pct, rs.overall_pct,
    d.ret_passing_yards, d.ret_rushing_yards, d.ret_receiving_yards, d.ret_receptions,
    d.ret_tackles, d.ret_sacks, d.ret_tackles_for_loss, d.ret_interceptions,
    d.weighted_off_pct, d.weighted_def_pct, d.weighted_overall_pct,
    cur.wins - prev.wins AS delta_wins,
    cur.win_pct - prev.win_pct AS delta_win_pct,
    cur.sp_rating - prev.sp_rating AS delta_sp
FROM returning_detail d
JOIN returning_summary rs ON rs.team_id = d.team_id AND rs.season = d.season
JOIN teams t ON t.team_id = d.team_id
JOIN team_outcomes cur  ON cur.team_id = d.team_id AND cur.season = d.season
JOIN team_outcomes prev ON prev.team_id = d.team_id AND prev.season = d.season - 1
WHERE d.season BETWEEN :start AND :end
"""


def steiger_z(r12: float, r13: float, r23: float, n: int) -> tuple[float, float]:
    """Steiger's z for two dependent correlations sharing variable 1."""
    det = 1 - r12**2 - r13**2 - r23**2 + 2 * r12 * r13 * r23
    avg = (r12 + r13) / 2
    z12, z13 = np.arctanh(r12), np.arctanh(r13)
    cov = (r23 * (1 - 2 * avg**2) - 0.5 * avg**2 * (1 - 2 * avg**2 - r23**2)) / (1 - avg**2) ** 2
    z = (z12 - z13) * math.sqrt((n - 3) / (2 * (1 - cov)))
    p = 2 * (1 - stats.norm.cdf(abs(z)))
    return z, p


def load_dataset(start: int, end: int, include_covid: bool) -> pd.DataFrame:
    df = pd.read_sql(text(DATASET_SQL), engine, params={"start": start, "end": end})
    if not include_covid:
        excluded = int(df["season"].isin([2020, 2021]).sum())
        print(f"excluding {excluded} COVID-distorted rows (2020/2021)")
        df = df[~df["season"].isin([2020, 2021])]
    share_cols = ["overall_pct", "off_pct", "def_pct"]
    out_of_range = (df[share_cols].lt(0) | df[share_cols].gt(1)).any(axis=1)
    if out_of_range.any():
        print(f"dropped {int(out_of_range.sum())} rows with shares outside [0,1]")
        df = df[~out_of_range]
    return df


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--start-season", type=int, default=2015)
    parser.add_argument("--end-season", type=int, default=2025)
    parser.add_argument("--include-covid", action="store_true")
    args = parser.parse_args()

    df = load_dataset(args.start_season, args.end_season, args.include_covid)
    print(f"n={len(df)}, seasons {df['season'].min()}-{df['season'].max()}")

    rows = []
    for x in PREDICTORS:
        for y in OUTCOMES:
            sub = df[[x, y]].dropna()
            if len(sub) < 30:
                continue
            slope, _ = np.polyfit(sub[x], sub[y], 1)
            rows.append({
                "predictor": x, "outcome": y, "n": len(sub),
                "pearson_r": sub[x].corr(sub[y]),
                "spearman_r": sub[x].corr(sub[y], method="spearman"),
                "ols_slope": slope,
            })
    table = pd.DataFrame(rows)
    print("\nCorrelations (identical row set per pair):")
    print(table.round(3).to_string(index=False))

    # Steiger's z: weighted_overall vs overall against delta_sp on shared rows
    shared = df[["overall_pct", "weighted_overall_pct", "delta_sp"]].dropna()
    r_base = shared["delta_sp"].corr(shared["overall_pct"])
    r_weighted = shared["delta_sp"].corr(shared["weighted_overall_pct"])
    r_between = shared["overall_pct"].corr(shared["weighted_overall_pct"])
    z, p = steiger_z(r_weighted, r_base, r_between, len(shared))
    print(f"\nSteiger's z (weighted vs baseline, outcome delta_sp, n={len(shared)}):")
    print(f"  r(baseline)={r_base:.3f}  r(weighted)={r_weighted:.3f}  "
          f"r(between)={r_between:.3f}  z={z:.2f}  p={p:.3f}")
    verdict = "weighted better" if r_weighted > r_base else "baseline better"
    print(f"  verdict: {verdict}" + (" (significant)" if p < 0.10 else " (not significant)"))

    print("\nBuckets on weighted_overall_pct:")
    bucketed = df.dropna(subset=["weighted_overall_pct"]).assign(
        bucket=pd.cut(df["weighted_overall_pct"], BUCKET_EDGES, labels=BUCKET_LABELS))
    print(bucketed.groupby("bucket", observed=True)
          .agg(n=("bucket", "size"),
               mean_delta_wins=("delta_wins", "mean"),
               mean_delta_sp=("delta_sp", "mean"))
          .round(3).to_string())

    print("\nNote: LOSO out-of-sample r for the weighted composite is reported by "
          "analysis/estimate_category_weights.py (0.227 at last estimation) and is the "
          "honest comparison against the baseline's 0.260.")


if __name__ == "__main__":
    main()
