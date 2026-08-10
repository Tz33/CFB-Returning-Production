# analysis/estimate_transfer_translation.py
"""Estimate how transfer production translates across conference tiers.

A mover is a player with meaningful stats at team U in season Y-1 who is ON
THE ROSTER of team T != U in season Y. Destination production comes from
stats at T in Y, COALESCEd to 0 — movers who never play count as zeros, so
the ratios are free of survivorship bias.

Prints per tier-pair (P->P, P->G, G->P, G->G) aggregate translation ratios
and a ready-to-paste block for db/translation.py. Portal era (2021+) only by
default; the pre-portal tail (~20-60 movers/yr) is too thin for coefficients.
"""
import argparse

import pandas as pd
from sqlalchemy import text

from db.session import engine
from db.tiers import conference_tier

MOVERS_SQL = """
SELECT
    o.player_id,
    r.position,
    o.season + 1     AS dest_season,
    ot.school        AS origin_school,
    oc.conference    AS origin_conference,
    dt.school        AS dest_school,
    dc.conference    AS dest_conference,
    o.{value_col}    AS origin_production,
    COALESCE(d.{value_col}, 0) AS dest_production
FROM player_stats_{side} o
JOIN rosters r
  ON r.player_id = o.player_id AND r.season = o.season + 1 AND r.team_id != o.team_id
JOIN teams ot ON ot.team_id = o.team_id
JOIN teams dt ON dt.team_id = r.team_id
LEFT JOIN team_seasons oc ON oc.team_id = o.team_id AND oc.season = o.season
LEFT JOIN team_seasons dc ON dc.team_id = r.team_id AND dc.season = r.season
LEFT JOIN player_stats_{side} d
  ON d.player_id = o.player_id AND d.season = r.season AND d.team_id = r.team_id
WHERE o.{value_col} >= :min_origin
  AND o.season + 1 BETWEEN :start AND :end
"""


def load_movers(side: str, value_col: str, min_origin: float, start: int, end: int) -> pd.DataFrame:
    sql = MOVERS_SQL.format(side=side, value_col=value_col)
    df = pd.read_sql(text(sql), engine,
                     params={"min_origin": min_origin, "start": start, "end": end})
    # tier of each endpoint; rows without a team_seasons entry are FCS-era — excluded, counted
    missing = df["origin_conference"].isna() | df["dest_conference"].isna()
    if missing.any():
        print(f"  excluded {int(missing.sum())} movers with a non-FBS endpoint")
        df = df[~missing]
    df = df.copy()
    df["origin_tier"] = df.apply(
        lambda r: conference_tier(r["origin_conference"], r["dest_season"] - 1, r["origin_school"]), axis=1)
    df["dest_tier"] = df.apply(
        lambda r: conference_tier(r["dest_conference"], r["dest_season"], r["dest_school"]), axis=1)
    return df


def translation_table(movers: pd.DataFrame) -> pd.DataFrame:
    grouped = movers.groupby(["origin_tier", "dest_tier"])
    return pd.DataFrame({
        "n": grouped.size(),
        "aggregate_ratio": grouped.apply(
            lambda g: g["dest_production"].sum() / g["origin_production"].sum(), include_groups=False),
        "median_ratio": grouped.apply(
            lambda g: (g["dest_production"] / g["origin_production"]).median(), include_groups=False),
        "zero_dest_share": grouped.apply(
            lambda g: (g["dest_production"] == 0).mean(), include_groups=False),
    }).round(3)


def position_table(movers: pd.DataFrame, positions: list[str], min_n: int = 40) -> pd.DataFrame:
    sub = movers[movers["position"].isin(positions)]
    grouped = sub.groupby(["position", "origin_tier", "dest_tier"])
    table = pd.DataFrame({
        "n": grouped.size(),
        "aggregate_ratio": grouped.apply(
            lambda g: g["dest_production"].sum() / g["origin_production"].sum(), include_groups=False),
    }).round(3)
    return table[table["n"] >= min_n]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--start-season", type=int, default=2021,
                        help="First destination season (portal era default)")
    parser.add_argument("--end-season", type=int, default=2025)
    parser.add_argument("--include-pre-portal", action="store_true",
                        help="Also print a 2015+ appendix table (too thin for coefficients)")
    args = parser.parse_args()

    results = {}
    for side, value_col, min_origin in (("offense", "total_yards", 100), ("defense", "tackles", 10)):
        print(f"\n=== {side} (origin {value_col} >= {min_origin}, "
              f"dest seasons {args.start_season}-{args.end_season}) ===")
        movers = load_movers(side, value_col, min_origin, args.start_season, args.end_season)
        print(f"  movers: {len(movers)}")
        table = translation_table(movers)
        print(table.to_string())
        results[side] = table

        positions = ["QB", "RB", "WR"] if side == "offense" else ["DL", "LB", "DB"]
        pos = position_table(movers, positions)
        if len(pos):
            print(f"\n  position cells with n >= 40:")
            print(pos.to_string())

        if args.include_pre_portal:
            pre = load_movers(side, value_col, min_origin, 2015, args.start_season - 1)
            print(f"\n  APPENDIX pre-portal ({len(pre)} movers — too thin for coefficients):")
            print(translation_table(pre).to_string())

    print("\n# paste into db/translation.py:")
    print(f"# provenance: analysis/estimate_transfer_translation.py, dest seasons "
          f"{args.start_season}-{args.end_season}, aggregate sum(dest)/sum(origin)")
    for side, table in results.items():
        entries = {f"('{o}', '{d}')": row["aggregate_ratio"]
                   for (o, d), row in table.iterrows()}
        body = ", ".join(f"{k}: {v}" for k, v in entries.items())
        print(f'    "{side}": {{{body}}},')


if __name__ == "__main__":
    main()
