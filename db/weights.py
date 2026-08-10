"""Per-category weights for the weighted returning-production composite.

Weights are estimated empirically by analysis/estimate_category_weights.py
(ridge regression of delta SP+ on standardized category shares, weight =
clipped-positive coefficient renormalized to sum 1). They are a descriptive
mixing scheme, not causal estimates. Empty dicts mean "not yet estimated";
compute_returning_detail leaves the weighted columns NULL in that case.
"""

# provenance: analysis/estimate_category_weights.py, seasons 2015-2025 (COVID
# excluded), n=887, ridge alpha=0.0, outcome=delta_sp, LOSO r=0.227.
# NOTE: the weighted composite UNDERPERFORMS the baseline overall_pct
# (LOSO r=0.227 vs 0.260 on identical rows) — kept for the category-level
# structure (receiving > passing > rushing, matching Connelly's published
# finding), not as a replacement predictor.
OFF_WEIGHTS: dict[str, float] = {
    "ret_passing_yards": 0.3272,
    "ret_rushing_yards": 0.2491,
    "ret_receiving_yards": 0.4236,
    "ret_receptions": 0.0,
}
DEF_WEIGHTS: dict[str, float] = {
    "ret_tackles": 0.0907,
    "ret_sacks": 0.0,
    "ret_tackles_for_loss": 0.571,
    "ret_interceptions": 0.3383,
}


def weighted_composite(shares: dict[str, float | None], weights: dict[str, float]) -> float | None:
    """Weighted average of the non-null shares, renormalizing weights over them."""
    if not weights:
        return None
    present = {k: v for k, v in shares.items() if v is not None and k in weights}
    total_weight = sum(weights[k] for k in present)
    if not present or total_weight == 0:
        return None
    return sum(v * weights[k] for k, v in present.items()) / total_weight
