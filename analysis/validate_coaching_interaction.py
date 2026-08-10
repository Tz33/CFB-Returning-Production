# analysis/validate_coaching_interaction.py
"""Does returning production predict less under a new head coach?

Splits the returning-production correlation by coaching continuity and fits
the interaction OLS: delta_sp ~ ret + new_coach + ret*new_coach.
Exploratory — the estimate and p-value either way are the deliverable.
"""
import argparse

import numpy as np
import pandas as pd
from scipy import stats
from sqlalchemy import text

from db.session import engine

DATASET_SQL = """
SELECT
    rs.season, t.school,
    rs.overall_pct,
    d.weighted_overall_pct,
    cc.new_head_coach, cc.is_interim, cc.coach_name,
    cur.wins - prev.wins AS delta_wins,
    cur.sp_rating - prev.sp_rating AS delta_sp
FROM returning_summary rs
JOIN teams t ON t.team_id = rs.team_id
JOIN coach_changes cc ON cc.team_id = rs.team_id AND cc.season = rs.season
LEFT JOIN returning_detail d ON d.team_id = rs.team_id AND d.season = rs.season
JOIN team_outcomes cur  ON cur.team_id = rs.team_id AND cur.season = rs.season
JOIN team_outcomes prev ON prev.team_id = rs.team_id AND prev.season = rs.season - 1
WHERE rs.season BETWEEN :start AND :end
"""


def interaction_ols(df: pd.DataFrame, predictor: str) -> dict:
    """OLS delta_sp ~ ret + new_coach + ret*new_coach with analytic SEs."""
    sub = df[[predictor, "new_coach", "delta_sp"]].dropna()
    x1 = sub[predictor].to_numpy()
    x2 = sub["new_coach"].to_numpy().astype(float)
    y = sub["delta_sp"].to_numpy()
    X = np.column_stack([np.ones_like(x1), x1, x2, x1 * x2])

    beta, _, _, _ = np.linalg.lstsq(X, y, rcond=None)
    resid = y - X @ beta
    dof = len(y) - X.shape[1]
    sigma2 = resid @ resid / dof
    cov = sigma2 * np.linalg.inv(X.T @ X)
    se = np.sqrt(np.diag(cov))
    t_stats = beta / se
    p_vals = 2 * (1 - stats.t.cdf(np.abs(t_stats), dof))
    return {
        "n": len(y),
        "b_ret": beta[1], "b_new_coach": beta[2],
        "b_interaction": beta[3], "se_interaction": se[3],
        "t_interaction": t_stats[3], "p_interaction": p_vals[3],
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--start-season", type=int, default=2015)
    parser.add_argument("--end-season", type=int, default=2025)
    parser.add_argument("--include-covid", action="store_true")
    parser.add_argument("--include-interim", action="store_true")
    args = parser.parse_args()

    df = pd.read_sql(text(DATASET_SQL), engine,
                     params={"start": args.start_season, "end": args.end_season})
    if not args.include_covid:
        df = df[~df["season"].isin([2020, 2021])]
    if not args.include_interim:
        n_interim = int((df["new_head_coach"] & df["is_interim"]).sum())
        print(f"excluding {n_interim} interim-coach seasons (--include-interim to keep)")
        df = df[~(df["new_head_coach"] & df["is_interim"])]
    df = df[(df["overall_pct"] >= 0) & (df["overall_pct"] <= 1)]
    df["new_coach"] = df["new_head_coach"].astype(bool)

    print(f"n={len(df)}: {int(df['new_coach'].sum())} new-coach team-seasons, "
          f"{int((~df['new_coach']).sum())} continuity")

    print("\nGroup means:")
    print(df.groupby("new_coach")[["delta_sp", "delta_wins"]].mean().round(3).to_string())

    print("\nSplit correlations vs delta_sp:")
    for predictor in ["overall_pct", "weighted_overall_pct"]:
        for flag, label in [(False, "continuity"), (True, "new coach")]:
            sub = df[df["new_coach"] == flag][[predictor, "delta_sp"]].dropna()
            print(f"  {predictor:>22} | {label:<10} r={sub[predictor].corr(sub['delta_sp']):.3f} (n={len(sub)})")

    print("\nInteraction OLS (delta_sp ~ ret + new_coach + ret*new_coach):")
    for predictor in ["overall_pct", "weighted_overall_pct"]:
        r = interaction_ols(df, predictor)
        print(f"  {predictor}: b_ret={r['b_ret']:.2f}  b_new_coach={r['b_new_coach']:.2f}  "
              f"interaction={r['b_interaction']:.2f} (SE {r['se_interaction']:.2f}, "
              f"t={r['t_interaction']:.2f}, p={r['p_interaction']:.3f}, n={r['n']})")

    n_new = int(df["new_coach"].sum())
    print(f"\nPower caveat: only {n_new} new-coach rows — interactions smaller than "
          f"~0.4 SD are not detectable at this sample size.")


if __name__ == "__main__":
    main()
