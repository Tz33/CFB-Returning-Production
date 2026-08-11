# model/game_prob.py
"""Rating gap -> win probability.

The curve is fitted on END-OF-SEASON SP+ ratings vs actual game results (the
standard mapping of rating gaps to win frequency) and applied to PREDICTED
preseason ratings. The rating model's noise widens effective uncertainty;
the backtest measures that end-to-end rather than correcting analytically.
"""
import numpy as np
import pandas as pd
from sqlalchemy import text

WIN_CURVE_SQL = """
SELECT
    ho.sp_rating AS rating_home,
    ao.sp_rating AS rating_away,
    g.neutral_site,
    (g.home_points > g.away_points)::int AS home_win
FROM games g
JOIN team_outcomes ho ON ho.team_id = g.home_team_id AND ho.season = g.season
JOIN team_outcomes ao ON ao.team_id = g.away_team_id AND ao.season = g.season
WHERE g.season BETWEEN 2015 AND :max_season
  AND g.season != 2020
  AND g.completed
  AND g.home_classification = 'fbs' AND g.away_classification = 'fbs'
  AND g.home_points IS NOT NULL AND g.away_points IS NOT NULL
  AND g.home_points != g.away_points
  AND ho.sp_rating IS NOT NULL AND ao.sp_rating IS NOT NULL
"""

FCS_SQL = """
SELECT
    CASE WHEN g.home_classification = 'fbs'
         THEN (g.home_points > g.away_points)::int
         ELSE (g.away_points > g.home_points)::int END AS fbs_win,
    fo.sp_rating AS fbs_rating
FROM games g
JOIN team_outcomes fo
  ON fo.season = g.season
 AND fo.team_id = CASE WHEN g.home_classification = 'fbs'
                       THEN g.home_team_id ELSE g.away_team_id END
WHERE g.season BETWEEN 2015 AND :max_season
  AND g.season != 2020
  AND g.completed
  AND g.home_points IS NOT NULL AND g.away_points IS NOT NULL
  AND ((g.home_classification = 'fbs') != (g.away_classification = 'fbs'))
  AND fo.sp_rating IS NOT NULL
"""


def sigmoid(z: np.ndarray) -> np.ndarray:
    return 1.0 / (1.0 + np.exp(-z))


def fit_logistic(X: np.ndarray, y: np.ndarray, max_iter: int = 50, tol: float = 1e-8) -> np.ndarray:
    """Newton-IRLS logistic MLE. X should already include an intercept column."""
    beta = np.zeros(X.shape[1])
    for _ in range(max_iter):
        p = sigmoid(X @ beta)
        W = p * (1 - p)
        grad = X.T @ (y - p)
        hess = X.T @ (X * W[:, None])
        step = np.linalg.solve(hess, grad)
        beta += step
        if np.max(np.abs(step)) < tol:
            break
    return beta


def fit_win_curve(engine, max_season: int) -> dict:
    """P(home win) = sigmoid(a + b*rating_diff + c*home_advantage)."""
    df = pd.read_sql(text(WIN_CURVE_SQL), engine, params={"max_season": max_season})
    X = np.column_stack([
        np.ones(len(df)),
        (df["rating_home"] - df["rating_away"]).to_numpy(float),
        (~df["neutral_site"].fillna(False)).astype(float).to_numpy(),
    ])
    beta = fit_logistic(X, df["home_win"].to_numpy(float))
    return {"beta": beta, "n": len(df)}


def fcs_win_curve(engine, max_season: int) -> dict:
    """P(FBS beats FCS) = sigmoid(a + b * FBS team's rating).

    A flat historical average made every FBS team equally likely to beat an
    FCS opponent, overstating weak-team wins and understating elite-team
    wins by a game's worth of tail probability. Fitted on final-season
    ratings and applied to predicted ones, like the main win curve; the
    backtest measures that mismatch end-to-end.
    """
    df = pd.read_sql(text(FCS_SQL), engine, params={"max_season": max_season})
    X = np.column_stack([np.ones(len(df)), df["fbs_rating"].to_numpy(float)])
    beta = fit_logistic(X, df["fbs_win"].to_numpy(float))
    return {"beta": beta, "n": len(df)}


def fcs_prob(rating: float, curve: dict) -> float:
    return float(sigmoid(np.array(curve["beta"][0] + curve["beta"][1] * rating)))


def game_prob(rating_home: float, rating_away: float, neutral: bool, beta: np.ndarray) -> float:
    z = beta[0] + beta[1] * (rating_home - rating_away) + beta[2] * (0.0 if neutral else 1.0)
    return float(sigmoid(np.array(z)))
