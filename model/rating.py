# model/rating.py
"""Expanding-window OLS rating model: predict a team's final SP+ rating from
preseason-knowable features.

Continuity enters as separate offensive and defensive features — the old
blended overall_pct gave offense ~90% weight purely because yards outnumber
tackles; here OLS fits the balance. Each side coalesces the portal-adjusted
index (2021+) with the raw returning share (earlier), with a portal_era dummy
absorbing the level shift. The portal adjustment's incremental value is
identified by the head-to-head against the raw-returning baseline (same rows,
raw shares in place of the adjusted indexes), not by the pooled coefficients.
Defensive shares for the 2015-2016 seasons rest on sparse CFBD stats (see
README data caveats), so early folds fit the defensive coefficient on noise.
"""
import numpy as np
import pandas as pd

FEATURES = ["sp_prev", "continuity_off", "continuity_def",
            "new_head_coach", "recruit_z", "portal_era", "is_new_fbs"]
# baseline (b): identical spec but raw returning shares replace the portal-adjusted indexes
BASELINE_FEATURES = ["sp_prev", "off_pct", "def_pct",
                     "new_head_coach", "recruit_z", "portal_era", "is_new_fbs"]
COVID_SEASONS = {2020, 2021}


def fit_ols(X: np.ndarray, y: np.ndarray, feature_names: list[str]) -> dict:
    """OLS with analytic standard errors; X gets an intercept column prepended."""
    Xd = np.column_stack([np.ones(len(X)), X])
    beta, _, _, _ = np.linalg.lstsq(Xd, y, rcond=None)
    resid = y - Xd @ beta
    dof = len(y) - Xd.shape[1]
    sigma2 = resid @ resid / dof
    cov = sigma2 * np.linalg.inv(Xd.T @ Xd)
    se = np.sqrt(np.diag(cov))
    return {
        "features": feature_names,
        "beta": beta,
        "se": se,
        "t": beta / se,
        "n": len(y),
        "sigma2": sigma2,
    }


def expanding_window_fit(df: pd.DataFrame, eval_season: int,
                         features: list[str] = FEATURES) -> dict:
    """Fit on target seasons strictly before eval_season, excluding COVID and interim rows."""
    train = df[
        (df["season"] < eval_season)
        & ~df["season"].isin(COVID_SEASONS)
        & ~df["is_interim"]
        & df["sp_rating"].notna()
    ].dropna(subset=features)
    assert train["season"].max() < eval_season, "time-safety violated"
    # constant columns (e.g. portal_era in pre-2022 windows) are collinear with the intercept
    usable = [f for f in features if train[f].nunique() > 1]
    return fit_ols(train[usable].to_numpy(float), train["sp_rating"].to_numpy(float), usable)


def predict_ratings(rows: pd.DataFrame, fit: dict) -> pd.Series:
    X = np.column_stack([np.ones(len(rows)), rows[fit["features"]].to_numpy(float)])
    return pd.Series(X @ fit["beta"], index=rows.index)


def coefficient_table(fit: dict) -> pd.DataFrame:
    from scipy import stats
    dof = fit["n"] - len(fit["beta"])
    return pd.DataFrame({
        "feature": ["intercept"] + fit["features"],
        "beta": fit["beta"],
        "se": fit["se"],
        "t": fit["t"],
        "p": 2 * (1 - stats.t.cdf(np.abs(fit["t"]), dof)),
    })
