# model/features.py
"""Leakage-free feature frame for the rating model.

One row per (season, team): the target is that season's final SP+ rating;
every feature is knowable before the season starts (prior SP+, returning
production, coaching change, recruiting class, returning OL starts).

Offensive-line continuity (`continuity_ol`) is deliberately its own term rather
than a component of the yards-based continuity indexes: linemen accrue no
box-score stats, so it is a games-started share (NCAA GP/GS), not a yards
share, and the model fits its weight instead of assuming a blend.
"""
import pandas as pd
from sqlalchemy import text

PORTAL_ERA_START = 2022  # first non-COVID season with portal-adjusted continuity

FEATURE_SQL = """
SELECT
    rs.season,
    rs.team_id,
    t.school,
    cur.sp_rating                    AS sp_rating,
    prev.sp_rating                   AS sp_prev,
    rs.overall_pct,
    rs.off_pct,
    rs.def_pct,
    rd.adjusted_overall_pct,
    rd.adjusted_off_pct,
    rd.adjusted_def_pct,
    rd.weighted_def_pct,
    rd.ret_ol_starts_share,
    cc.new_head_coach,
    cc.is_interim,
    rec.points                       AS recruit_points
FROM returning_summary rs
JOIN teams t ON t.team_id = rs.team_id
LEFT JOIN returning_detail rd ON rd.team_id = rs.team_id AND rd.season = rs.season
LEFT JOIN team_outcomes cur  ON cur.team_id = rs.team_id AND cur.season = rs.season
LEFT JOIN team_outcomes prev ON prev.team_id = rs.team_id AND prev.season = rs.season - 1
LEFT JOIN coach_changes cc ON cc.team_id = rs.team_id AND cc.season = rs.season
LEFT JOIN recruiting rec ON rec.team_id = rs.team_id AND rec.season = rs.season
WHERE rs.season BETWEEN :start AND :end
  AND rs.overall_pct BETWEEN 0 AND 1
"""


def build_features(engine, start: int = 2015, end: int = 2026) -> pd.DataFrame:
    df = pd.read_sql(text(FEATURE_SQL), engine, params={"start": start, "end": end})
    return derive_features(df)


def derive_features(df: pd.DataFrame) -> pd.DataFrame:
    """Derive model columns from the raw FEATURE_SQL frame (pure; no DB access)."""
    df = df.copy()

    # separate sides: the blended overall_pct weights offense ~90% by the
    # accident of yards vs tackles units; the model fits the balance instead
    df["continuity_off"] = df["adjusted_off_pct"].fillna(df["off_pct"])
    df["continuity_def"] = df["adjusted_def_pct"].fillna(df["def_pct"])

    # OL continuity: returning share of prior-season OL games started. Clip the
    # rare >1 share (roster/name-match noise); the few teams without NCAA rows or
    # a roster get the season mean (pooled mean when a whole season lacks OL data,
    # e.g. 2015) — a mean-imputed row contributes no fitted OL effect and keeps
    # the training set identical to the no-OL spec.
    df["continuity_ol"] = pd.to_numeric(df["ret_ol_starts_share"], errors="coerce").clip(0, 1)
    df["continuity_ol"] = df.groupby("season")["continuity_ol"].transform(
        lambda s: s.fillna(s.mean()))
    df["continuity_ol"] = df["continuity_ol"].fillna(df["continuity_ol"].mean())

    df["portal_era"] = (df["season"] >= PORTAL_ERA_START).astype(float)
    df["new_head_coach"] = df["new_head_coach"].astype(object).fillna(False).astype(float)
    df["is_interim"] = df["is_interim"].astype(object).fillna(False).astype(bool)

    # recruiting: fill missing with the season's FBS minimum, then z-score within season
    df["recruit_points"] = df.groupby("season")["recruit_points"].transform(
        lambda s: s.fillna(s.min()))
    df["recruit_z"] = df.groupby("season")["recruit_points"].transform(
        lambda s: (s - s.mean()) / (s.std() or 1.0))

    # FBS newcomers have no prior SP+: impute at the season's 5th percentile and flag
    df["is_new_fbs"] = df["sp_prev"].isna().astype(float)
    df["sp_prev"] = df.groupby("season")["sp_prev"].transform(
        lambda s: s.fillna(s.quantile(0.05)))

    return df
