# model/simulate.py
"""Season simulation: per-game win probabilities -> exact win distribution."""
import numpy as np
import pandas as pd
from sqlalchemy import text

from model.game_prob import game_prob

SCHEDULE_SQL = """
SELECT game_id, home_team_id, away_team_id, home_classification, away_classification,
       neutral_site, completed, home_points, away_points
FROM games
WHERE season = :season AND season_type = 'regular'
  AND (home_classification = 'fbs' OR away_classification = 'fbs')
"""


def win_distribution(probs: list[float]) -> np.ndarray:
    """Poisson-binomial via DP. Exact; O(n^2) with n <= ~13 games."""
    dist = np.zeros(len(probs) + 1)
    dist[0] = 1.0
    for i, p in enumerate(probs):
        for k in range(i + 1, 0, -1):
            dist[k] = dist[k] * (1 - p) + dist[k - 1] * p
        dist[0] *= (1 - p)
    return dist


def team_game_probs(schedule: pd.DataFrame, ratings: dict[int, float],
                    beta: np.ndarray, fcs_prob: float,
                    completed_only: bool = False) -> dict[int, list[dict]]:
    """Per FBS team: list of {game_id, prob, won} over its scheduled games.

    FBS opponents missing a predicted rating (e.g., no returning metrics) get
    the 5th percentile of the rating pool. `won` is None for unplayed games.
    """
    fallback = float(np.quantile(list(ratings.values()), 0.05)) if ratings else 0.0
    out: dict[int, list[dict]] = {tid: [] for tid in ratings}

    for row in schedule.itertuples():
        if completed_only and not row.completed:
            continue
        for team_id, opp_id, opp_class, is_home in (
            (row.home_team_id, row.away_team_id, row.away_classification, True),
            (row.away_team_id, row.home_team_id, row.home_classification, False),
        ):
            if team_id not in out:
                continue
            if opp_class == "fcs" or opp_id is None:
                prob = fcs_prob
            else:
                own = ratings[team_id]
                opp = ratings.get(opp_id, fallback)
                if is_home:
                    prob = game_prob(own, opp, bool(row.neutral_site), beta)
                else:
                    prob = 1.0 - game_prob(opp, own, bool(row.neutral_site), beta)
            won = None
            if row.completed and row.home_points is not None and row.away_points is not None:
                won = (row.home_points > row.away_points) == is_home
            out[team_id].append({"game_id": row.game_id, "prob": prob, "won": won})
    return out


def simulate_season(engine, season: int, ratings: dict[int, float],
                    beta: np.ndarray, fcs_prob: float,
                    completed_only: bool = False) -> pd.DataFrame:
    schedule = pd.read_sql(text(SCHEDULE_SQL), engine, params={"season": season})
    per_team = team_game_probs(schedule, ratings, beta, fcs_prob, completed_only)

    rows = []
    for team_id, games in per_team.items():
        if not games:
            continue
        probs = [g["prob"] for g in games]
        dist = win_distribution(probs)
        wins_known = [g["won"] for g in games if g["won"] is not None]
        rows.append({
            "team_id": team_id,
            "n_games": len(probs),
            "expected_wins": float(np.sum(probs)),
            "p_ge_6": float(dist[6:].sum()) if len(dist) > 6 else 0.0,
            "p_ge_8": float(dist[8:].sum()) if len(dist) > 8 else 0.0,
            "p_ge_10": float(dist[10:].sum()) if len(dist) > 10 else 0.0,
            "win_dist": dist,
            "actual_wins": sum(wins_known) if wins_known else None,
            "n_completed": len(wins_known),
        })
    return pd.DataFrame(rows)
