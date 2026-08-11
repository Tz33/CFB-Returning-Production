# model/simulate.py
"""Season simulation: per-game win probabilities -> exact win distribution."""
import numpy as np
import pandas as pd
from sqlalchemy import text

from model.calibration import recalibrate
from model.game_prob import fcs_prob, game_prob

SCHEDULE_SQL = """
SELECT g.game_id, g.home_team_id, g.away_team_id, g.home_classification,
       g.away_classification, g.neutral_site, g.completed, g.home_points,
       g.away_points, g.week,
       hs.conference AS home_conf, aw.conference AS away_conf
FROM games g
LEFT JOIN team_seasons hs ON hs.team_id = g.home_team_id AND hs.season = g.season
LEFT JOIN team_seasons aw ON aw.team_id = g.away_team_id AND aw.season = g.season
WHERE g.season = :season AND g.season_type = 'regular'
  AND (g.home_classification = 'fbs' OR g.away_classification = 'fbs')
"""


def drop_ccgs(schedule: pd.DataFrame) -> pd.DataFrame:
    """Remove conference championship games from a season schedule.

    CFBD files CCGs under season_type='regular', so a completed season's
    schedule contains matchups determined by that season's results — outcome
    information a preseason projection cannot have, and games that sportsbook
    win totals exclude. No CFBD flag marks them reliably (2025 CCGs carry
    conference_game=False), so identify them structurally: championship week
    is the first week > 12 with 5-20 FBS games (full weeks run 50+, the lone
    Army-Navy week runs 1), and a CCG is a same-conference matchup that week.
    When a conference has several same-conference games that week (2022 MAC:
    snow-displaced Buffalo-Akron alongside the title game), the neutral-site
    one is the CCG. Preseason schedules list no CCG matchups, so this is a
    no-op for live projections.
    """
    counts = schedule.groupby("week")["game_id"].count()
    champ_weeks = [w for w, n in counts.items() if w > 12 and 5 <= n <= 20]
    if not champ_weeks:
        return schedule
    wk = schedule[schedule["week"] == min(champ_weeks)]
    same_conf = wk[wk["home_conf"].notna() & (wk["home_conf"] == wk["away_conf"])
                   & (wk["home_conf"] != "FBS Independents")]
    drop_ids: list[int] = []
    for _, group in same_conf.groupby("home_conf"):
        if len(group) == 1:
            drop_ids.extend(group["game_id"])
        else:
            neutral = group[group["neutral_site"].fillna(False).astype(bool)]
            if len(neutral) == 1:
                drop_ids.extend(neutral["game_id"])
    return schedule[~schedule["game_id"].isin(drop_ids)]


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
                    beta: np.ndarray, fcs_curve: dict,
                    completed_only: bool = False,
                    calibration: dict[str, float] | None = None) -> dict[int, list[dict]]:
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
                # rating-conditioned empirical curve; not Platt-recalibrated
                # (the Platt fit covers FBS-vs-FBS raw probs only)
                prob = fcs_prob(ratings[team_id], fcs_curve)
            else:
                own = ratings[team_id]
                opp = ratings.get(opp_id, fallback)
                if is_home:
                    prob = recalibrate(game_prob(own, opp, bool(row.neutral_site), beta), calibration)
                else:
                    prob = 1.0 - recalibrate(game_prob(opp, own, bool(row.neutral_site), beta), calibration)
            won = None
            if row.completed and row.home_points is not None and row.away_points is not None:
                won = (row.home_points > row.away_points) == is_home
            out[team_id].append({"game_id": row.game_id, "prob": prob, "won": won})
    return out


def simulate_season(engine, season: int, ratings: dict[int, float],
                    beta: np.ndarray, fcs_curve: dict,
                    completed_only: bool = False,
                    calibration: dict[str, float] | None = None) -> pd.DataFrame:
    schedule = drop_ccgs(pd.read_sql(text(SCHEDULE_SQL), engine, params={"season": season}))
    per_team = team_game_probs(schedule, ratings, beta, fcs_curve, completed_only, calibration)

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
