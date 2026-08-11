# analysis/backtest_win_projections.py
"""Time-safe backtest of the win-projection pipeline.

For each eval season (2019, 2022-2025): rating model, win curve, FCS prob,
AND Platt calibration are fit strictly on earlier seasons; the eval season's
actual completed regular-season games are simulated; expected wins are scored
against actual wins counted over the exact same game set. Metrics: MAE vs two
baselines, market win-total hit rates (overall and on the portal-divergence
subset), and calibration of the win distributions.

Market hit-rate p-values use a program-clustered bootstrap (teams repeat
across seasons and share games, so pooled team-seasons are not IID Bernoulli
trials); per-season binomial p's in the detail table are descriptive only.

Conference championship games are excluded from every simulated schedule
(model.simulate.drop_ccgs): their matchups are determined by season results
and sportsbook totals exclude them. They do remain in the Platt-fitting game
pool — there they are ordinary completed prob/outcome pairs from pre-fold
seasons, not schedule composition.
"""
import argparse

import numpy as np
import pandas as pd
from scipy import stats
from sqlalchemy import text

from db.session import engine
from model.features import build_features
from model.rating import (FEATURES, BASELINE_FEATURES, COVID_SEASONS,
                          expanding_window_fit, predict_ratings)
from model.game_prob import fit_logistic, fit_win_curve, fcs_win_prob, game_prob
from model.simulate import SCHEDULE_SQL, simulate_season

EVAL_SEASONS = [2019, 2022, 2023, 2024, 2025]
CAL_START = 2016  # earliest season with a trainable expanding-window fit behind it

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
                  curve: dict, fcs_p: float, platt: dict[str, float]) -> pd.DataFrame:
    fit = expanding_window_fit(features_df, season, feature_set)
    target = features_df[features_df["season"] == season].dropna(subset=feature_set).copy()
    target["rating_pred"] = predict_ratings(target, fit)
    ratings = dict(zip(target["team_id"], target["rating_pred"]))
    sim = simulate_season(engine, season, ratings, curve["beta"], fcs_p,
                          completed_only=True, calibration=platt)
    return sim.dropna(subset=["actual_wins"])


def carry_forward_fold(season: int, features_df: pd.DataFrame,
                       curve: dict, fcs_p: float, platt: dict[str, float]) -> pd.DataFrame:
    target = features_df[features_df["season"] == season].dropna(subset=["sp_prev"]).copy()
    ratings = dict(zip(target["team_id"], target["sp_prev"]))
    sim = simulate_season(engine, season, ratings, curve["beta"], fcs_p,
                          completed_only=True, calibration=platt)
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


_raw_probs_cache: dict[int, pd.DataFrame] = {}


def expanding_platt(eval_season: int, features_df: pd.DataFrame) -> dict[str, float]:
    """Platt constants fit on raw probs from seasons strictly before eval_season
    (COVID excluded, matching the rating fit), so the calibration layer is as
    time-safe as the rest of the fold."""
    cal_seasons = [s for s in range(CAL_START, eval_season) if s not in COVID_SEASONS]
    for s in cal_seasons:
        if s not in _raw_probs_cache:
            _raw_probs_cache[s] = collect_raw_game_probs(s, features_df)
    pooled = pd.concat([_raw_probs_cache[s] for s in cal_seasons])
    return fit_platt(pooled)


def hit_records(sub: pd.DataFrame) -> pd.DataFrame:
    """Per-team-season market outcomes (pushes dropped): team_id + hit 0/1."""
    sub = sub[(sub["lean"] != 0) & (sub["result"] != 0)]
    return pd.DataFrame({"team_id": sub["team_id"].to_numpy(),
                         "hit": (sub["lean"] == sub["result"]).astype(int).to_numpy()})


def hit_stats(sub: pd.DataFrame) -> tuple[int, int, float]:
    recs = hit_records(sub)
    n, wins = len(recs), int(recs["hit"].sum())
    p = stats.binomtest(wins, n, 0.5).pvalue if n else float("nan")
    return wins, n, p


def cluster_bootstrap(records: pd.DataFrame, n_boot: int = 10000,
                      seed: int = 0) -> dict[str, float]:
    """Two-sided p and 95% CI for the pooled hit rate vs 0.5, resampling
    programs (team_id clusters) so repeat appearances of the same team across
    seasons don't inflate the effective sample size."""
    by_team = records.groupby("team_id")["hit"].agg(["sum", "size"])
    h = by_team["sum"].to_numpy(float)
    c = by_team["size"].to_numpy(float)
    rng = np.random.default_rng(seed)
    idx = rng.integers(0, len(h), size=(n_boot, len(h)))
    rates = h[idx].sum(axis=1) / c[idx].sum(axis=1)
    lo = (np.count_nonzero(rates <= 0.5) + 1) / (n_boot + 1)
    hi = (np.count_nonzero(rates >= 0.5) + 1) / (n_boot + 1)
    return {"p": min(1.0, 2 * min(lo, hi)),
            "ci_lo": float(np.quantile(rates, 0.025)),
            "ci_hi": float(np.quantile(rates, 0.975))}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--quantile", type=float, default=0.8,
                        help="Divergence-subset cutoff (0.8 = top quintile)")
    parser.add_argument("--fit-calibration", action="store_true",
                        help="Fit Platt on pooled folds and print PRODUCTION constants "
                             "for model/calibration.py (the backtest itself now uses "
                             "fold-specific pre-eval calibration, not these)")
    args = parser.parse_args()

    features_df = build_features(engine, start=2015, end=2026)

    if args.fit_calibration:
        pooled = pd.concat([collect_raw_game_probs(s, features_df) for s in EVAL_SEASONS])
        platt = fit_platt(pooled)
        print(f"# Platt fit on {len(pooled)} pooled backtest games "
              f"(seasons {EVAL_SEASONS}) — paste into model/calibration.py:")
        print(f"CALIBRATION: dict[str, float] = {platt}")
        return

    mae_rows, market_rows, calib_rows, market_mae_rows = [], [], [], []
    all_records: dict[str, list] = {"model": [], "baseline_raw_ret": []}
    div_records: dict[str, list] = {"model": [], "baseline_raw_ret": []}
    for season in EVAL_SEASONS:
        curve = fit_win_curve(engine, max_season=season - 1)
        fcs_p = fcs_win_prob(engine, max_season=season - 1)
        platt = expanding_platt(season, features_df)

        sims = {
            "model": simulate_fold(season, features_df, FEATURES, curve, fcs_p, platt),
            "baseline_raw_ret": simulate_fold(season, features_df, BASELINE_FEATURES, curve, fcs_p, platt),
            "baseline_carry": carry_forward_fold(season, features_df, curve, fcs_p, platt),
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
            if name == "model":
                market_mae_rows.append(
                    joined[["season", "expected_wins", "win_total", "actual_wins"]])
            wins, n, p = hit_stats(joined)
            all_records[name].append(hit_records(joined))
            row = {"season": season, "variant": name, "hits": wins, "n": n, "p": p}
            if not gaps.empty:
                div = joined.merge(divergence_subset(gaps, args.quantile), on="team_id")
                d_wins, d_n, d_p = hit_stats(div)
                div_records[name].append(hit_records(div))
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
    print("(p-values: program-clustered bootstrap vs 0.5; per-season binomial "
          "p's below are descriptive only)")
    mk = pd.DataFrame(market_rows)
    for name in ("model", "baseline_raw_ret"):
        pooled = pd.concat(all_records[name])
        hits, n = int(pooled["hit"].sum()), len(pooled)
        boot = cluster_bootstrap(pooled)
        line = (f"  {name}: {hits}/{n} = {hits / n:.3f} "
                f"(cluster p={boot['p']:.3f}, 95% CI {boot['ci_lo']:.3f}-{boot['ci_hi']:.3f})")
        if div_records[name]:
            div_pooled = pd.concat(div_records[name])
            dh, dn = int(div_pooled["hit"].sum()), len(div_pooled)
            dboot = cluster_bootstrap(div_pooled)
            line += (f" | divergence subset: {dh}/{dn} = {dh / dn:.3f} "
                     f"(cluster p={dboot['p']:.3f}, 95% CI {dboot['ci_lo']:.3f}-{dboot['ci_hi']:.3f})")
        print(line)
    print(mk.round(3).to_string(index=False))

    print("\n=== Market MAE benchmark (same market-covered team-seasons; "
          "actual wins exclude CCGs, matching book totals) ===")
    mm = pd.concat(market_mae_rows)
    mm["model_ae"] = (mm["expected_wins"] - mm["actual_wins"]).abs()
    mm["market_ae"] = (mm["win_total"] - mm["actual_wins"]).abs()
    print(mm.groupby("season")[["model_ae", "market_ae"]].mean().round(3).to_string())
    print(f"pooled: model {mm['model_ae'].mean():.3f}, market {mm['market_ae'].mean():.3f} "
          f"(n={len(mm)})")

    print("\n=== Calibration (pooled across folds) ===")
    calib = pd.concat(calib_rows)
    calib["bucket"] = pd.cut(calib["pred"], [0, 0.25, 0.5, 0.75, 1.0001],
                             labels=["0-25%", "25-50%", "50-75%", "75-100%"])
    print(calib.groupby(["threshold", "bucket"], observed=True)
          .agg(n=("realized", "size"), predicted=("pred", "mean"), realized=("realized", "mean"))
          .round(3).to_string())

    print("\nCaveats: The 2019 fold has no portal signal by construction; "
          "divergence claims rest on 2022-2025.")


if __name__ == "__main__":
    main()
