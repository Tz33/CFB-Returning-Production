# model/calibration.py
"""Platt recalibration of curve-based game probabilities.

The win curve is fitted on final-season ratings but applied to noisier
predicted preseason ratings, which makes raw tail probabilities overconfident
(backtest: predicted 93% bowl prob realized 81%). A single logistic
recalibration prob' = sigmoid(alpha + gamma * logit(prob)) with gamma < 1
pulls tails toward the center. Coefficients are fitted on pooled backtest
folds via analysis/backtest_win_projections.py --fit-calibration.

Empty dict = identity (used while fitting the calibration itself).
"""
import math

# provenance: analysis/backtest_win_projections.py --fit-calibration,
# 3,743 pooled completed games from time-safe folds 2019/2022-2025
CALIBRATION: dict[str, float] = {"alpha": 0.0809, "gamma": 0.6563}


def recalibrate(prob: float, params: dict[str, float] | None = None) -> float:
    """Apply Platt constants; `params=None` uses the production CALIBRATION,
    backtests pass fold-specific constants fit on pre-fold seasons only."""
    if params is None:
        params = CALIBRATION
    if not params:
        return prob
    prob = min(max(prob, 1e-9), 1 - 1e-9)
    z = params["alpha"] + params["gamma"] * math.log(prob / (1 - prob))
    return 1.0 / (1.0 + math.exp(-z))
