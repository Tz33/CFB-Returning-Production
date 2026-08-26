import numpy as np
import pandas as pd

from model.features import derive_features


def _raw(rows: list[dict]) -> pd.DataFrame:
    base = {
        "school": "X", "sp_rating": 5.0, "sp_prev": 3.0, "overall_pct": 0.6,
        "off_pct": 0.6, "def_pct": 0.5, "adjusted_overall_pct": None,
        "adjusted_off_pct": None, "adjusted_def_pct": None, "weighted_def_pct": None,
        "ret_ol_starts_share": None, "new_head_coach": False, "is_interim": False,
        "recruit_points": 200.0,
    }
    return pd.DataFrame([{**base, **r} for r in rows])


def test_continuity_ol_clips_and_imputes_season_mean():
    df = _raw([
        {"season": 2024, "team_id": 1, "ret_ol_starts_share": 0.4},
        {"season": 2024, "team_id": 2, "ret_ol_starts_share": 0.8},
        {"season": 2024, "team_id": 3, "ret_ol_starts_share": None},   # no NCAA rows
        {"season": 2024, "team_id": 4, "ret_ol_starts_share": 1.2},    # name-match noise
        {"season": 2015, "team_id": 1, "ret_ol_starts_share": None},   # season with no OL data
        {"season": 2015, "team_id": 2, "ret_ol_starts_share": None},
    ])
    out = derive_features(df)
    assert out["continuity_ol"].notna().all()
    s24 = out[out["season"] == 2024].set_index("team_id")["continuity_ol"]
    assert s24[4] == 1.0                                  # clipped
    assert np.isclose(s24[3], np.mean([0.4, 0.8, 1.0]))   # season mean of observed, post-clip
    pooled = np.mean([0.4, 0.8, 1.0])
    assert np.allclose(out[out["season"] == 2015]["continuity_ol"], pooled)  # pooled fallback
    assert len(out) == len(df)                            # no rows dropped


def test_continuity_off_coalesces_adjusted_over_raw():
    df = _raw([
        {"season": 2024, "team_id": 1, "off_pct": 0.5, "adjusted_off_pct": 1.1},
        {"season": 2024, "team_id": 2, "off_pct": 0.5, "adjusted_off_pct": None},
    ])
    out = derive_features(df).set_index("team_id")
    assert out.loc[1, "continuity_off"] == 1.1
    assert out.loc[2, "continuity_off"] == 0.5
