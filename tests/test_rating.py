import numpy as np
import pandas as pd

from model.rating import (BASELINE_FEATURES, FEATURES, NO_OL_FEATURES,
                          expanding_window_fit)


def test_ol_term_in_model_and_baseline_but_not_ablation():
    assert "continuity_ol" in FEATURES
    assert "continuity_ol" in BASELINE_FEATURES
    assert "continuity_ol" not in NO_OL_FEATURES
    assert NO_OL_FEATURES == [f for f in FEATURES if f != "continuity_ol"]


def _synthetic(seed: int = 0, per_season: int = 80) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    rows = []
    for season in range(2016, 2025):
        n = per_season
        sp_prev = rng.normal(0, 12, n)
        off = rng.uniform(0.3, 1.1, n)
        de = rng.uniform(0.3, 1.0, n)
        ol = rng.uniform(0.0, 1.0, n)
        coach = (rng.uniform(size=n) < 0.2).astype(float)
        rec = rng.normal(0, 1, n)
        y = (-8 + 0.6 * sp_prev + 10 * off + 2 * de + 5 * ol - 1.5 * coach + 3 * rec
             + rng.normal(0, 4, n))
        rows.append(pd.DataFrame({
            "season": season, "sp_rating": y, "sp_prev": sp_prev, "continuity_off": off,
            "continuity_def": de, "continuity_ol": ol, "new_head_coach": coach,
            "recruit_z": rec, "portal_era": float(season >= 2022), "is_new_fbs": 0.0,
            "is_interim": False,
        }))
    return pd.concat(rows, ignore_index=True)


def test_expanding_window_fit_recovers_ol_coefficient():
    df = _synthetic()
    fit = expanding_window_fit(df, 2025)
    beta = dict(zip(fit["features"], fit["beta"][1:]))  # beta[0] is the intercept
    assert np.isfinite(beta["continuity_ol"])
    assert abs(beta["continuity_ol"] - 5.0) < 1.5
    assert abs(beta["continuity_off"] - 10.0) < 2.0
    assert fit["n"] == len(df[~df["season"].isin({2020, 2021})])


def test_no_ol_spec_fits_on_identical_rows():
    df = _synthetic()
    full = expanding_window_fit(df, 2025, FEATURES)
    ablation = expanding_window_fit(df, 2025, NO_OL_FEATURES)
    assert full["n"] == ablation["n"]
    assert "continuity_ol" not in ablation["features"]
