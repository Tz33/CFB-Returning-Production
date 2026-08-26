# model/run_projections.py
"""Fit the rating model on history and project the target season's win totals.

Usage: python -m model.run_projections --season 2026
"""
import argparse
import json

import pandas as pd

from db.session import SessionLocal, engine
from db.models import WinProjection
from model.features import build_features
from model.rating import FEATURES, expanding_window_fit, predict_ratings, coefficient_table
from model.game_prob import fit_win_curve, fcs_win_curve, fcs_prob
from model.simulate import simulate_season

MODEL_VERSION = "v3-ols-ol-continuity"


def project_season(season: int) -> pd.DataFrame:
    df = build_features(engine, start=2015, end=season)

    fit = expanding_window_fit(df, season, FEATURES)
    print(f"rating model fit: n={fit['n']} team-seasons (targets 2015-{season - 1}, COVID excluded)")
    print(coefficient_table(fit).round(3).to_string(index=False))

    target = df[df["season"] == season].dropna(subset=FEATURES).copy()
    target["rating_pred"] = predict_ratings(target, fit)
    ratings = dict(zip(target["team_id"], target["rating_pred"]))

    curve = fit_win_curve(engine, max_season=season - 1)
    fcs_c = fcs_win_curve(engine, max_season=season - 1)
    print(f"\nwin curve (n={curve['n']}): intercept={curve['beta'][0]:.3f} "
          f"per-SP+-point={curve['beta'][1]:.4f} home-field={curve['beta'][2]:.3f}; "
          f"FCS curve (n={fcs_c['n']}): p at SP+ -10/0/+20 = "
          f"{fcs_prob(-10, fcs_c):.3f}/{fcs_prob(0, fcs_c):.3f}/{fcs_prob(20, fcs_c):.3f}")

    sim = simulate_season(engine, season, ratings, curve["beta"], fcs_c)
    sim = sim.merge(target[["team_id", "school", "rating_pred"]], on="team_id")
    return sim.sort_values("expected_wins", ascending=False)


def store_projections(sim: pd.DataFrame, season: int) -> None:
    with SessionLocal() as s:
        s.query(WinProjection).filter(WinProjection.season == season).delete()
        for row in sim.itertuples():
            s.add(WinProjection(
                season=season,
                team_id=row.team_id,
                rating_pred=float(row.rating_pred),
                n_games=int(row.n_games),
                expected_wins=float(row.expected_wins),
                p_ge_6=float(row.p_ge_6),
                p_ge_8=float(row.p_ge_8),
                p_ge_10=float(row.p_ge_10),
                win_dist=json.dumps([round(float(p), 5) for p in row.win_dist]),
                model_version=MODEL_VERSION,
            ))
        s.commit()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--season", type=int, default=2026)
    args = parser.parse_args()

    sim = project_season(args.season)
    store_projections(sim, args.season)

    print(f"\n{args.season} win projections ({len(sim)} teams):")
    view = sim[["school", "rating_pred", "n_games", "expected_wins", "p_ge_6", "p_ge_8", "p_ge_10"]]
    print(view.round(3).to_string(index=False))


if __name__ == "__main__":
    main()
