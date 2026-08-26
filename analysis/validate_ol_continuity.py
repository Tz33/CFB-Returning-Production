# analysis/validate_ol_continuity.py
"""Measure whether returning OL starts share predicts next-season improvement.

Joins returning_detail.ret_ol_starts_share (season Y) with team_outcomes at
Y and Y-1, reports correlations and bucket summaries for delta wins / delta
SP+, and — the decision gate — an incremental OLS: does the OL share add
signal beyond the overall returning-production share the model already uses?

--full-spec runs the same incremental test inside the production rating spec
(model.rating.NO_OL_FEATURES: prior SP+, split continuity, coaching change,
recruiting, era dummies) on the model's own feature frame, i.e. the
coefficient the projections will actually use. The target there is the SP+
level; with prior SP+ as a regressor the OL coefficient is identical to the
delta-SP+ formulation.
"""
import argparse
import os

import numpy as np
import pandas as pd
from sqlalchemy import text

from db.session import engine

BUCKET_EDGES = [0, 0.25, 0.5, 0.75, 1.0001]
BUCKET_LABELS = ["<25%", "25-50%", "50-75%", "75%+"]

DATASET_SQL = """
SELECT
    rd.season,
    t.school,
    rd.ret_ol_starts_share,
    rs.overall_pct,
    cur.wins,
    cur.sp_rating,
    prev.wins      AS wins_prev,
    prev.sp_rating AS sp_rating_prev
FROM returning_detail rd
JOIN teams t ON t.team_id = rd.team_id
LEFT JOIN returning_summary rs ON rs.team_id = rd.team_id AND rs.season = rd.season
JOIN team_outcomes cur  ON cur.team_id = rd.team_id AND cur.season = rd.season
JOIN team_outcomes prev ON prev.team_id = rd.team_id AND prev.season = rd.season - 1
WHERE rd.ret_ol_starts_share IS NOT NULL
  AND rd.season BETWEEN :start AND :end
"""


def load_dataset(start_season: int, end_season: int) -> pd.DataFrame:
    df = pd.read_sql(text(DATASET_SQL), engine, params={"start": start_season, "end": end_season})
    df["delta_wins"] = df["wins"] - df["wins_prev"]
    df["delta_sp"] = df["sp_rating"] - df["sp_rating_prev"]
    df["covid_flag"] = df["season"].isin([2020, 2021])
    return df


def correlations(df: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for y in ["delta_wins", "delta_sp"]:
        sub = df[["ret_ol_starts_share", y]].dropna()
        slope, _ = np.polyfit(sub["ret_ol_starts_share"], sub[y], 1)
        rows.append({
            "outcome": y,
            "n": len(sub),
            "pearson_r": sub["ret_ol_starts_share"].corr(sub[y]),
            "spearman_r": sub["ret_ol_starts_share"].corr(sub[y], method="spearman"),
            "ols_slope": slope,
        })
    return pd.DataFrame(rows)


def incremental_ols(df: pd.DataFrame, base_cols: tuple[str, ...] = ("overall_pct",),
                    target: str = "delta_sp", label: str | None = None) -> None:
    """target ~ base_cols vs target ~ base_cols + ol_share, with a
    season-clustered bootstrap p-value on the OL coefficient."""
    base_cols = tuple(base_cols)
    label = label or f"{target} ~ {' + '.join(base_cols)} [+ ret_ol_starts_share]"
    sub = df[["season", "ret_ol_starts_share", target, *base_cols]].dropna()
    if len(sub) < 50:
        print(f"\nIncremental OLS skipped: only {len(sub)} rows with {base_cols} available")
        return

    def fit(data: pd.DataFrame) -> tuple[float, float]:
        x1 = np.column_stack([np.ones(len(data)), data[list(base_cols)].to_numpy(float)])
        x2 = np.column_stack([x1, data["ret_ol_starts_share"].to_numpy(float)])
        y = data[target].to_numpy(float)
        b1 = np.linalg.lstsq(x1, y, rcond=None)[0]
        b2 = np.linalg.lstsq(x2, y, rcond=None)[0]
        # residuals computed explicitly: lstsq returns none for rank-deficient
        # draws (e.g. a bootstrap resample where an era dummy is constant)
        sst = ((y - y.mean()) ** 2).sum()
        r2_base = 1 - ((y - x1 @ b1) ** 2).sum() / sst
        r2_full = 1 - ((y - x2 @ b2) ** 2).sum() / sst
        return b2[-1], r2_full - r2_base

    coef, r2_gain = fit(sub)

    rng = np.random.default_rng(0)
    seasons = sub["season"].unique()
    boot = []
    for _ in range(2000):
        pick = rng.choice(seasons, size=len(seasons), replace=True)
        sample = pd.concat([sub[sub["season"] == s] for s in pick])
        boot.append(fit(sample)[0])
    boot = np.array(boot)
    p = 2 * min((boot <= 0).mean(), (boot >= 0).mean())

    print(f"\nIncremental OLS ({label}, n={len(sub)}, seasons={len(seasons)}):")
    print(f"  OL coefficient: {coef:+.2f} SP+ per unit share "
          f"(season-clustered bootstrap p={p:.3f}, 95% CI "
          f"[{np.percentile(boot, 2.5):+.2f}, {np.percentile(boot, 97.5):+.2f}])")
    print(f"  R^2 gain over the base spec: {r2_gain:+.4f}")


def full_spec_report(include_covid: bool) -> None:
    """The gate inside the production spec: observed OL shares only (no imputed
    rows), same row filters as model.rating.expanding_window_fit."""
    from model.features import build_features
    from model.rating import COVID_SEASONS, NO_OL_FEATURES

    df = build_features(engine)
    df = df[df["sp_rating"].notna() & ~df["is_interim"] & df["ret_ol_starts_share"].notna()].copy()
    if not include_covid:
        df = df[~df["season"].isin(COVID_SEASONS)]
    df["ret_ol_starts_share"] = pd.to_numeric(df["ret_ol_starts_share"], errors="coerce").clip(0, 1)
    missing = [f for f in NO_OL_FEATURES if df[f].isna().all()]
    if missing:
        print(f"\nWARNING: {missing} are entirely NULL in this database (loader not run?) — "
              f"dropped from the base spec; the OL coefficient below is not the production one.")
    base = tuple(f for f in NO_OL_FEATURES if f not in missing and df[f].nunique() > 1)
    print(f"\n=== Full production spec (n={len(df)}, seasons "
          f"{df['season'].min()}-{df['season'].max()}) ===")
    incremental_ols(df, base_cols=base, target="sp_rating",
                    label=f"sp_rating ~ {' + '.join(base)} [+ ret_ol_starts_share]")


def bucket_summary(df: pd.DataFrame) -> pd.DataFrame:
    bucketed = df.assign(bucket=pd.cut(df["ret_ol_starts_share"], BUCKET_EDGES,
                                       labels=BUCKET_LABELS, include_lowest=True))
    return (
        bucketed.groupby("bucket", observed=True)
        .agg(n=("bucket", "size"),
             mean_delta_wins=("delta_wins", "mean"),
             mean_delta_sp=("delta_sp", "mean"))
        .round(3)
    )


def report(df: pd.DataFrame, label: str) -> None:
    print(f"\n=== {label} (n={len(df)}, seasons {df['season'].min()}-{df['season'].max()}) ===")
    print("\nCorrelations (positive = more returning OL starts, bigger improvement):")
    print(correlations(df).round(3).to_string(index=False))
    print("\nBy returning-OL-starts bucket:")
    print(bucket_summary(df).to_string())
    incremental_ols(df)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--start-season", type=int, default=2016)
    parser.add_argument("--end-season", type=int, default=2025)
    parser.add_argument("--include-covid", action="store_true")
    parser.add_argument("--full-spec", action="store_true",
                        help="Also run the incremental test inside the production rating spec")
    parser.add_argument("--out", default=os.path.join("analysis", "output", "ol_continuity_merged.csv"))
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

    if args.full_spec:
        full_spec_report(args.include_covid)


if __name__ == "__main__":
    main()
