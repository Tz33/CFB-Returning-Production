# analysis/backtest_win_projections.py
"""Time-safe backtest of the win-projection pipeline.

For each eval season (2019, 2022-2025): rating model, win curve, and FCS prob
are fit strictly on earlier seasons; the eval season's actual completed
regular-season games are simulated; expected wins are scored against actual
wins counted over the exact same game set. Metrics: MAE vs two baselines,
market win-total hit rates (overall and on the portal-divergence subset),
and calibration of the win distributions.

Caveat printed in output: conference championship games sit inside CFBD's
regular season while sportsbook totals mostly exclude them — a small upward
bias in expected wins for contenders; noted, not corrected.
"""
import argparse

import numpy as np
import pandas as pd
from scipy import stats
from sqlalchemy import text

from db.session import engine
from model.features import build_features
from model.rating import FEATURES, BASELINE_FEATURES, expanding_window_fit, predict_ratings
from model.game_prob import fit_logistic, fit_win_curve, fcs_win_prob, game_prob
from model.simulate import SCHEDULE_SQL, simulate_season

EVAL_SEASONS = [2019, 2022, 2023, 2024, 2025]

MARKET_SQL = """
SELECT wt.season, wt.team_id, wt.win_total
FROM win_totals wt WHERE wt.season = :season
"""
DIVERGENCE_SQL = """
SELECT d.season, d.team_id,
       d.adjusted_overall_pct - rs.overall_pct AS gap
FROM returning_detail d
JOIN returning_summary rs ON rs.team_id = d.team_id AND rs.season = d.season
WHERE d.season = :season AND d.adjusted_overall_pct IS NOT NULL
"""


def divergence_subset(df: pd.DataFrame, quantile: float = 0.8) -> pd.DataFrame:
    """Rows in the top (1-quantile) tail of |portal-adjusted minus raw| gap."""
    cutoff = df["gap"].abs().quantile(quantile)
    return df[df["gap"].abs() >= cutoff]


def simulate_fold(season: int, features_df: pd.DataFrame, feature_set: list[str],
                  curve: dict, fcs_p: float) -> pd.DataFrame:
    fit = expanding_window_fit(features_df, season, feature_set)
    target = features_df[features_df["season"] == season].dropna(subset=feature_set).copy()
    target["rating_pred"] = predict_ratings(target, fit)
    ratings = dict(zip(target["team_id"], target["rating_pred"]))
    sim = simulate_season(engine, season, ratings, curve["beta"], fcs_p, completed_only=True)
    return sim.dropna(subset=["actual_wins"])


def carry_forward_fold(season: int, features_df: pd.DataFrame,
                       curve: dict, fcs_p: float) -> pd.DataFrame:
    target = features_df[features_df["season"] == season].dropna(subset=["sp_prev"]).copy()
    ratings = dict(zip(target["team_id"], target["sp_prev"]))
    sim = simulate_season(engine, season, ratings, curve["beta"], fcs_p, completed_only=True)
    return sim.dropna(subset=["actual_wins"])


def collect_raw_game_probs(season: int, features_df: pd.DataFrame) -> pd.DataFrame:
    """Home-perspective RAW (uncalibrated) probs vs outcomes for completed
    FBS-vs-FBS games, using time-safe predicted ratings. For Platt fitting."""
    curve = fit_win_curve(engine, max_season=season - 1)
    fit = expanding_window_fit(features_df, season, FEATURES)
    target = features_df[features_df["season"] == season].dropna(subset=FEATURES).copy()
    target["rating_pred"] = predict_ratings(target, fit)
    ratings = dict(zip(target["team_id"], target["rating_pred"]))

    schedule = pd.read_sql(text(SCHEDULE_SQL), engine, params={"season": season})
    rows = []
    for g in schedule.itertuples():
        if (not g.completed or g.home_points is None or g.away_points is None
                or g.home_points == g.away_points
                or g.home_team_id not in ratings or g.away_team_id not in ratings):
            continue
        rows.append({
            "prob": game_prob(ratings[g.home_team_id], ratings[g.away_team_id],
                              bool(g.neutral_site), curve["beta"]),
            "home_win": float(g.home_points > g.away_points),
        })
    return pd.DataFrame(rows)


def fit_platt(games: pd.DataFrame) -> dict[str, float]:
    logit = np.log(games["prob"].clip(1e-9, 1 - 1e-9) / (1 - games["prob"].clip(1e-9, 1 - 1e-9)))
    X = np.column_stack([np.ones(len(games)), logit.to_numpy()])
    beta = fit_logistic(X, games["home_win"].to_numpy())
    return {"alpha": round(float(beta[0]), 4), "gamma": round(float(beta[1]), 4)}


def hit_stats(sub: pd.DataFrame) -> tuple[int, int, float]:
    sub = sub[(sub["lean"] != 0) & (sub["result"] != 0)]
    n, wins = len(sub), int((sub["lean"] == sub["result"]).sum())
    p = stats.binomtest(wins, n, 0.5).pvalue if n else float("nan")
    return wins, n, p


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--quantile", type=float, default=0.8,
                        help="Divergence-subset cutoff (0.8 = top quintile)")
    parser.add_argument("--fit-calibration", action="store_true",
                        help="Fit Platt recalibration on pooled folds and print the "
                             "coefficients for model/calibration.py")
    args = parser.parse_args()

    features_df = build_features(engine, start=2015, end=2026)

    if args.fit_calibration:
        pooled = pd.concat([collect_raw_game_probs(s, features_df) for s in EVAL_SEASONS])
        platt = fit_platt(pooled)
        print(f"# Platt fit on {len(pooled)} pooled backtest games "
              f"(seasons {EVAL_SEASONS}) — paste into model/calibration.py:")
        print(f"CALIBRATION: dict[str, float] = {platt}")
        return

    mae_rows, market_rows, calib_rows = [], [], []
    for season in EVAL_SEASONS:
        curve = fit_win_curve(engine, max_season=season - 1)
        fcs_p = fcs_win_prob(engine, max_season=season - 1)

        sims = {
            "model": simulate_fold(season, features_df, FEATURES, curve, fcs_p),
            "baseline_raw_ret": simulate_fold(season, features_df, BASELINE_FEATURES, curve, fcs_p),
            "baseline_carry": carry_forward_fold(season, features_df, curve, fcs_p),
        }
        for name, sim in sims.items():
            mae_rows.append({
                "season": season, "variant": name, "n": len(sim),
                "mae": (sim["expected_wins"] - sim["actual_wins"]).abs().mean(),
            })

        market = pd.read_sql(text(MARKET_SQL), engine, params={"season": season})
        gaps = pd.read_sql(text(DIVERGENCE_SQL), engine, params={"season": season})
        for name in ("model", "baseline_raw_ret"):
            joined = sims[name].merge(market, on="team_id")
            joined["lean"] = np.sign(joined["expected_wins"] - joined["win_total"])
            joined["result"] = np.sign(joined["actual_wins"] - joined["win_total"])
            wins, n, p = hit_stats(joined)
            row = {"season": season, "variant": name, "hits": wins, "n": n, "p": p}
            if not gaps.empty:
                div = joined.merge(divergence_subset(gaps, args.quantile), on="team_id")
                d_wins, d_n, d_p = hit_stats(div)
                row.update({"div_hits": d_wins, "div_n": d_n, "div_p": d_p})
            market_rows.append(row)

        for threshold, col in ((6, "p_ge_6"), (8, "p_ge_8")):
            sim = sims["model"]
            calib_rows.append(pd.DataFrame({
                "season": season, "threshold": threshold,
                "pred": sim[col], "realized": (sim["actual_wins"] >= threshold).astype(float),
            }))

    print("=== MAE: expected vs actual wins (identical completed-game sets) ===")
    mae = pd.DataFrame(mae_rows).pivot(index="season", columns="variant", values="mae").round(3)
    print(mae.to_string())
    print("\npooled:", mae.mean().round(3).to_dict())

    print("\n=== Market hit rates (lean vs preseason win totals) ===")
    mk = pd.DataFrame(market_rows)
    for name in ("model", "baseline_raw_ret"):
        sub = mk[mk["variant"] == name]
        hits, n = int(sub["hits"].sum()), int(sub["n"].sum())
        p = stats.binomtest(hits, n, 0.5).pvalue if n else float("nan")
        line = f"  {name}: {hits}/{n} = {hits / n:.3f} (p={p:.3f})"
        if sub["div_n"].notna().any():
            dh, dn = int(sub["div_hits"].sum()), int(sub["div_n"].sum())
            dp = stats.binomtest(dh, dn, 0.5).pvalue if dn else float("nan")
            line += f" | divergence subset: {dh}/{dn} = {dh / dn:.3f} (p={dp:.3f})"
        print(line)
    print(mk.round(3).to_string(index=False))

    print("\n=== Calibration (pooled across folds) ===")
    calib = pd.concat(calib_rows)
    calib["bucket"] = pd.cut(calib["pred"], [0, 0.25, 0.5, 0.75, 1.0001],
                             labels=["0-25%", "25-50%", "50-75%", "75-100%"])
    print(calib.groupby(["threshold", "bucket"], observed=True)
          .agg(n=("realized", "size"), predicted=("pred", "mean"), realized=("realized", "mean"))
          .round(3).to_string())

    print("\nCaveats: CCGs are inside CFBD regular season, book totals mostly exclude them "
          "(small upward bias for contenders). The 2019 fold has no portal signal by "
          "construction; divergence claims rest on 2022-2025.")


if __name__ == "__main__":
    main()
