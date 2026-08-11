# analysis/fold_translation.py
"""Fold-safe transfer translation for the backtest.

db.translation constants are estimated on destination seasons 2021-2025, so
2022-2024 backtest folds consumed coefficients partly estimated on their own
and later seasons. This module re-derives tier-pair ratios per fold from
destination seasons strictly before the eval season — shrunk toward 1.0
(production at face value) with a pseudo-count prior where early windows are
thin — and rebuilds the continuity features with them.

The recomputation mirrors etl.compute_returning_detail exactly: adjusted
side index = raw returning share + translated incoming production / prior
team total, incoming has no origin-production threshold, non-FBS origins are
skipped, and teams with a zero prior total keep the raw share. Feeding the
production db.translation coefficients through this path reproduces the
DB-stored adjusted indexes.
"""
import pandas as pd
from sqlalchemy import text

from analysis.estimate_transfer_translation import load_movers, translation_table
from db.tiers import conference_tier

ADJUSTED_START = 2021  # first portal-era destination season
SHRINK_K = 25  # pseudo-movers at ratio 1.0 blended into each tier-pair cell

_INCOMING_SQL = """
SELECT r.season, r.team_id,
       oc.conference AS origin_conference, ot.school AS origin_school,
       SUM(o.{value_col}) AS origin_sum
FROM rosters r
JOIN player_stats_{side} o
  ON o.player_id = r.player_id AND o.season = r.season - 1 AND o.team_id != r.team_id
JOIN teams ot ON ot.team_id = o.team_id
LEFT JOIN team_seasons oc ON oc.team_id = o.team_id AND oc.season = o.season
WHERE r.season >= :start
GROUP BY 1, 2, 3, 4
"""

_TOTAL_SQL = """
SELECT season + 1 AS season, team_id, SUM({value_col}) AS total
FROM player_stats_{side}
GROUP BY 1, 2
"""

_DEST_SQL = """
SELECT ts.season, ts.team_id, ts.conference, t.school
FROM team_seasons ts JOIN teams t ON t.team_id = ts.team_id
WHERE ts.season >= :start
"""

_SIDES = (("offense", "total_yards", 100), ("defense", "tackles", 10))


def fold_coefficients(eval_season: int, shrink_k: int = SHRINK_K) -> dict:
    """Tier-pair aggregate ratios from dest seasons 2021..eval_season-1.

    Shrinkage: (n * ratio + shrink_k * 1.0) / (n + shrink_k), so thin cells
    lean toward face-value production instead of a noisy estimate.
    """
    out: dict[str, dict[tuple[str, str], float]] = {}
    for side, value_col, min_origin in _SIDES:
        table = translation_table(
            load_movers(side, value_col, min_origin, ADJUSTED_START, eval_season - 1))
        out[side] = {
            pair: round((row["n"] * row["aggregate_ratio"] + shrink_k) / (row["n"] + shrink_k), 4)
            for pair, row in table.iterrows()
        }
    return out


class FoldTranslator:
    """Caches incoming-production tier sums once; applies any coefficient set."""

    def __init__(self, engine):
        dest = pd.read_sql(text(_DEST_SQL), engine, params={"start": ADJUSTED_START})
        dest["dest_tier"] = [conference_tier(c, s, sch) for c, s, sch in
                             zip(dest["conference"], dest["season"], dest["school"])]
        self._dest = dest.set_index(["season", "team_id"])["dest_tier"]

        self._incoming: dict[str, pd.DataFrame] = {}
        self._totals: dict[str, pd.Series] = {}
        for side, value_col, _ in _SIDES:
            inc = pd.read_sql(text(_INCOMING_SQL.format(side=side, value_col=value_col)),
                              engine, params={"start": ADJUSTED_START})
            inc = inc[inc["origin_conference"].notna()].copy()
            inc["origin_tier"] = [conference_tier(c, s - 1, sch) for c, s, sch in
                                  zip(inc["origin_conference"], inc["season"],
                                      inc["origin_school"])]
            inc["dest_tier"] = [self._dest.get(k) for k in
                                zip(inc["season"], inc["team_id"])]
            inc = inc[inc["dest_tier"].notna()]
            self._incoming[side] = (inc.groupby(["season", "team_id", "origin_tier", "dest_tier"])
                                    ["origin_sum"].sum().reset_index())
            totals = pd.read_sql(
                text(_TOTAL_SQL.format(side=side, value_col=value_col)),
                engine).set_index(["season", "team_id"])["total"]
            # zero prior totals have no adjusted index in the ETL either —
            # dropping them here routes those teams to the raw-share fallback
            self._totals[side] = totals[totals > 0]

    def boosts(self, coeffs: dict) -> pd.DataFrame:
        """[season, team_id, boost_off, boost_def]: translated incoming
        production as a share of the prior-season team total. Adjusted side
        index = raw share + boost; missing rows mean no incoming (boost 0)."""
        sides = {}
        for side, name in (("offense", "boost_off"), ("defense", "boost_def")):
            inc = self._incoming[side]
            translated = inc["origin_sum"] * [
                coeffs[side].get((o, d), 1.0)
                for o, d in zip(inc["origin_tier"], inc["dest_tier"])]
            summed = translated.groupby([inc["season"], inc["team_id"]]).sum()
            sides[name] = (summed / self._totals[side]).dropna()
        out = pd.concat(sides, axis=1).reset_index()
        return out


def apply_translation(features_df: pd.DataFrame, boosts: pd.DataFrame) -> pd.DataFrame:
    """Rebuild continuity features from raw shares plus coefficient boosts."""
    df = features_df.merge(boosts, on=["season", "team_id"], how="left")
    for feat, raw, boost in (("continuity_off", "off_pct", "boost_off"),
                             ("continuity_def", "def_pct", "boost_def")):
        df[feat] = (df[raw] + df[boost]).fillna(df[raw])
    return df.drop(columns=["boost_off", "boost_def"])
