# analysis/estimate_category_weights.py
"""Estimate per-category returning-production weights from historical data.

Fits ridge regressions of delta SP+ on standardized category shares
(offense and defense separately), selects the ridge alpha by
leave-one-season-out (LOSO) cross-validation, and prints a ready-to-paste
weights block for db/weights.py. The headline number is the LOSO
out-of-sample correlation of the weighted composite — the in-sample r is
optimistically biased because weights are fit on the same rows.
"""
import argparse

import numpy as np
import pandas as pd
from sqlalchemy import text

from db.session import engine
from db.weights import weighted_composite

OFF_CATS = ["ret_passing_yards", "ret_rushing_yards", "ret_receiving_yards", "ret_receptions"]
DEF_CATS = ["ret_tackles", "ret_sacks", "ret_tackles_for_loss", "ret_interceptions"]
ALPHAS = [0.0, 0.1, 1.0, 10.0]

DATASET_SQL = """
SELECT
    d.season,
    t.school,
    d.ret_passing_yards, d.ret_rushing_yards, d.ret_receiving_yards, d.ret_receptions,
    d.ret_tackles, d.ret_sacks, d.ret_tackles_for_loss, d.ret_interceptions,
    rs.overall_pct,
    cur.sp_rating - prev.sp_rating AS delta_sp,
    (SELECT COALESCE(SUM(o.total_yards), 0) FROM player_stats_offense o
      WHERE o.team_id = d.team_id AND o.season = d.season - 1) AS off_total_prev,
    (SELECT COALESCE(SUM(pd.tackles), 0) FROM player_stats_defense pd
      WHERE pd.team_id = d.team_id AND pd.season = d.season - 1) AS def_total_prev
FROM returning_detail d
JOIN teams t ON t.team_id = d.team_id
JOIN returning_summary rs ON rs.team_id = d.team_id AND rs.season = d.season
JOIN team_outcomes cur  ON cur.team_id = d.team_id AND cur.season = d.season
JOIN team_outcomes prev ON prev.team_id = d.team_id AND prev.season = d.season - 1
WHERE d.season BETWEEN :start AND :end
  AND cur.sp_rating IS NOT NULL AND prev.sp_rating IS NOT NULL
"""


def load_dataset(start: int, end: int, include_covid: bool = False) -> pd.DataFrame:
    df = pd.read_sql(text(DATASET_SQL), engine, params={"start": start, "end": end})
    if not include_covid:
        df = df[~df["season"].isin([2020, 2021])]
    share_cols = OFF_CATS + DEF_CATS + ["overall_pct"]
    out_of_range = (df[share_cols].lt(0) | df[share_cols].gt(1)).any(axis=1)
    if out_of_range.any():
        print(f"dropped {int(out_of_range.sum())} rows with shares outside [0,1]")
        df = df[~out_of_range]
    return df


def fit_ridge(X: np.ndarray, y: np.ndarray, alpha: float) -> np.ndarray:
    """Closed-form ridge on standardized columns; returns raw coefficients."""
    mu, sigma = X.mean(axis=0), X.std(axis=0)
    sigma[sigma == 0] = 1.0
    Xs = (X - mu) / sigma
    n_features = Xs.shape[1]
    coefs = np.linalg.solve(Xs.T @ Xs + alpha * np.eye(n_features), Xs.T @ (y - y.mean()))
    return coefs


def to_weights(coefs: np.ndarray, cats: list[str]) -> dict[str, float]:
    """Clip negative coefficients to zero and renormalize to sum 1 (descriptive mixing scheme)."""
    clipped = np.clip(coefs, 0, None)
    if clipped.sum() == 0:
        return {c: 1.0 / len(cats) for c in cats}
    normed = clipped / clipped.sum()
    return {c: round(float(w), 4) for c, w in zip(cats, normed)}


def blended_composite(row: pd.Series, off_w: dict, def_w: dict) -> float | None:
    off = weighted_composite({c: row[c] for c in OFF_CATS}, off_w)
    de = weighted_composite({c: row[c] for c in DEF_CATS}, def_w)
    off_t, def_t = row["off_total_prev"], row["def_total_prev"]
    if off is not None and de is not None and (off_t + def_t) > 0:
        return (off * off_t + de * def_t) / (off_t + def_t)
    if off is not None and def_t == 0:
        return off
    if de is not None and off_t == 0:
        return de
    return None


def loso_composites(df: pd.DataFrame, alpha: float) -> pd.Series:
    """For each season, fit weights on the other seasons and score the held-out rows."""
    out = pd.Series(index=df.index, dtype=float)
    for season in sorted(df["season"].unique()):
        train = df[df["season"] != season].dropna(subset=OFF_CATS + DEF_CATS + ["delta_sp"])
        off_w = to_weights(fit_ridge(train[OFF_CATS].to_numpy(), train["delta_sp"].to_numpy(), alpha), OFF_CATS)
        def_w = to_weights(fit_ridge(train[DEF_CATS].to_numpy(), train["delta_sp"].to_numpy(), alpha), DEF_CATS)
        held = df[df["season"] == season]
        out.loc[held.index] = held.apply(blended_composite, axis=1, args=(off_w, def_w))
    return out


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--start-season", type=int, default=2015)
    parser.add_argument("--end-season", type=int, default=2025)
    parser.add_argument("--include-covid", action="store_true")
    args = parser.parse_args()

    df = load_dataset(args.start_season, args.end_season, args.include_covid)
    print(f"dataset: n={len(df)}, seasons {df['season'].min()}-{df['season'].max()}")

    baseline = df["overall_pct"].corr(df["delta_sp"])
    print(f"baseline r(overall_pct, delta_sp) on this row set: {baseline:.3f}")

    print("\nLOSO alpha selection:")
    best_alpha, best_r = None, -np.inf
    for alpha in ALPHAS:
        composite = loso_composites(df, alpha)
        r = composite.corr(df["delta_sp"])
        marker = ""
        if r > best_r:
            best_alpha, best_r = alpha, r
            marker = "  <- best"
        print(f"  alpha={alpha:>5}: LOSO r={r:.3f}{marker}")

    print(f"\nheadline: LOSO out-of-sample r={best_r:.3f} (alpha={best_alpha}) "
          f"vs baseline {baseline:.3f}")

    fit = df.dropna(subset=OFF_CATS + DEF_CATS + ["delta_sp"])
    off_w = to_weights(fit_ridge(fit[OFF_CATS].to_numpy(), fit["delta_sp"].to_numpy(), best_alpha), OFF_CATS)
    def_w = to_weights(fit_ridge(fit[DEF_CATS].to_numpy(), fit["delta_sp"].to_numpy(), best_alpha), DEF_CATS)

    in_sample = fit.apply(blended_composite, axis=1, args=(off_w, def_w)).corr(fit["delta_sp"])
    print(f"in-sample r with final weights (biased upward): {in_sample:.3f}")

    print("\n# paste into db/weights.py:")
    print(f"# provenance: analysis/estimate_category_weights.py, seasons "
          f"{args.start_season}-{args.end_season} (COVID excluded), n={len(fit)}, "
          f"ridge alpha={best_alpha}, outcome=delta_sp, LOSO r={best_r:.3f}")
    print(f"OFF_WEIGHTS: dict[str, float] = {off_w}")
    print(f"DEF_WEIGHTS: dict[str, float] = {def_w}")


if __name__ == "__main__":
    main()
