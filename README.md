# CFB Returning Production

Utilities for loading CollegeFootballData rosters and stats into Postgres, computing returning and incoming production summaries, and validating that returning production predicts year-over-year team success.

## Setup

1. Install dependencies with `pip install -r requirements.txt`.
2. Set `CFBD_API_KEY` in your environment or a `.env` file before running ETL scripts.
3. Configure the database connection via `DATABASE_URL` in `.env` (see `.env.example`; use `127.0.0.1` rather than `localhost` on Windows — IPv6 fallback makes `localhost` connections hang for ~2 minutes).
4. `docker compose -f infra/docker-compose.yml up -d` starts Postgres (5432) and Adminer (8080).
5. `alembic upgrade head` applies all migrations.

## Historical backfill and validation

```
python -m etl.backfill --start-year 2014 --end-year 2025
python -m analysis.validate_returning_production
```

The backfill runs stages `teams -> rosters -> stats -> outcomes -> refresh -> returning -> incoming` (each skippable via `--only` / `--skip`) using one bulk API call per year per dataset (~60 calls total). The analysis script joins `returning_summary` with `team_outcomes` (wins and SP+ ratings) at seasons Y and Y-1 and reports correlations, OLS slopes, and bucket summaries; it writes the merged dataset to `analysis/output/`.

Individual loaders also support `--bulk` (all teams, one call per year) alongside the original `--team` / `--all` modes, e.g. `python -m etl.load_rosters --bulk --year 2024`.

### Validation results (2015-2025, COVID pairs excluded, n=1212)

Returning production correlates with year-over-year improvement: overall returning share vs SP+ change r = 0.26, vs win change r = 0.19. The bucket means are monotonic — teams returning <40% of production averaged -0.73 wins and -3.0 SP+ vs the prior year, while teams returning 80%+ averaged +1.06 wins and +3.8 SP+. Offensive returning production carries nearly all of the signal (off r = 0.25 vs def r = 0.07 against SP+ change).

### Differentiation features (2026-08 milestone)

- **Per-category weights** (`analysis/estimate_category_weights.py` -> `db/weights.py`): offense ordering matches Connelly (receiving .42 > passing .33 > rushing .25). The weighted overall composite ties the baseline (LOSO r=.227 vs .260 — the simple share already captures the signal), but the defensive weighting (TFL/INT-heavy) lifts defensive predictive power from r=.07 to r=.21.
- **Transfer translation** (`analysis/estimate_transfer_translation.py` -> `db/translation.py`): from 2,828 portal-era movers, G5->P4 transfers keep ~58-64% of production, P4->G5 gain ~50%, same-tier ~1.0. The **portal-adjusted continuity index** (returning + translated incoming production, 2021+) is the milestone headline: the plain metric collapsed to r=.157 in 2022-2025, the adjusted index restores r=.254 (Steiger p=.004). Teams above 100% adjusted continuity averaged +1.9 wins.
- **Coaching continuity** (`analysis/validate_coaching_interaction.py`): new-coach teams average -1.1 SP+ vs +0.3 under continuity; the returning-production interaction is directionally negative but not significant — no correction applied.
- **Market benchmarks**: early-season spreads (`analysis/validate_market_spreads.py`) show the market already prices returning production (extreme-quintile betting 52.8%, p=.14, no early/late attenuation). Preseason win totals are not in CFBD — fill `data/win_totals.csv` from the committed template and run `python -m etl.load_win_totals`, then `python -m analysis.validate_win_totals`.

## Offensive line continuity (NCAA GP/GS pipeline)

OL production is invisible to every stat-based returning metric (linemen accrue no
box-score stats, and CFBD has no snap or participation data). The workaround is
games started, scraped from stats.ncaa.org roster pages, which list GP/GS for all
players — OL included — back a decade-plus:

```
# 1. Collect: stats.ncaa.org blocks plain HTTP clients, so the scrape runs in a
#    real browser — see instructions at the top of etl/scrape_ncaa_participation.js.
#    Output lands in data/participation/<season>.csv.
python -m etl.load_participation                   # 2. load CSVs -> player_participation
python -m etl.compute_ol_continuity                # 3. ret_ol_starts_share -> returning_detail
```

`ret_ol_starts_share` = prior-season games started by OL who are on this season's
CFBD roster ÷ all prior-season OL games started. NCAA and CFBD share no player ids,
so "returning" is a normalized-name match (`db/names.py`: diacritics, punctuation,
and Jr./Sr./III suffixes stripped). Denominators are self-checking: a team's OL
starts should be ≈ 5 × games played. The feature is deliberately separate from the
production-share composites — it is a starts share, not a yards share — and must
earn model weight through the validation harness before it enters projections.

## Win projections (2026-08 milestone)

```
python -m model.run_projections --season 2026      # fit, simulate, store win_projections
python -m analysis.backtest_win_projections        # time-safe backtest vs baselines + market
python -m analysis.divergence_board                # the portal divergence board
```

The model predicts each team's SP+ rating from preseason-knowable features (prior SP+ .61, portal-adjusted offensive continuity +11.0, defensive continuity +1.9 (p=.02), new head coach -1.8, recruiting z +3.3). Continuity enters as separate fitted offense/defense features — the old blended index gave offense ~90% weight by the accident of yards-vs-tackles units; the fitted balance lands near 85/15, so the accident was close to right, but now it's a measurement instead of a coincidence. The model converts rating gaps to per-game win probabilities (logistic on 7,769 games: .128/SP+ point, home field +.30; FCS opponents get a rating-conditioned curve — ~86% for bottom-tier teams to 99.7% for elite, replacing a flat 93.7% that treated Alabama and a 2-win G5 team identically), applies Platt recalibration (gamma=.66, fixes tail overconfidence from predicted-rating noise), and sums exact Poisson-binomial win distributions over the real schedule (conference championship games excluded — their matchups encode season outcomes and book totals exclude them; see `model.simulate.drop_ccgs`).

**Backtest (2019, 2022-2025, everything fit strictly pre-season — rating model, win curve, FCS curve, Platt calibration, and transfer-translation coefficients are all re-derived per fold from prior seasons only; CCGs excluded throughout):** MAE 1.69 wins vs 1.71 (raw-returning baseline) and 1.83 (carry-forward); **55.6% against market win totals (232/417, program-clustered bootstrap p=.037, 95% CI .504-.607)**, with the model at or above the raw-returning baseline in 4 of 5 folds. On the portal-divergence subset the model hits **56.2% vs 50.0%** for an otherwise-identical raw-returning model — the portal adjustment earns its edge where published returning production is most wrong, though n=80 keeps that split directional. On identical market-covered team-seasons the model's MAE (1.73) edges the posted totals' own MAE (1.76), winning 4 of 5 seasons — market-grade accuracy from a free-data pipeline. The fold-safe translation coefficients drift across windows (offensive G5→P4 from ~0.86 on 2021-only data to ~0.64 by 2025) yet the results hold, so the adjustment's value doesn't depend on knowing the mature coefficients in advance. (Earlier drafts quoted 58.1%/p=.001; that figure leaked CCG outcomes into the schedule, pooled Platt calibration across eval folds, used translation coefficients estimated through 2025 in earlier folds, and tested with an IID binomial — all corrected here.)

### Model caveats

- CCG detection is structural (first week >12 with 5-20 FBS games, same-conference matchup): validated exact on 2019-2025, including the 2022 snow-displaced Buffalo-Akron game and Army-Navy, but re-verify if CFBD relabels weeks.
- The 2019 backtest fold has no portal signal by construction; divergence claims rest on 2022-2025 (n=80 market-covered divergence teams).
- The divergence gap is one-sided (incoming production only adds); the complementary view is the lowest-adjusted-continuity "depleted" table.
- August rosters are preseason snapshots — rerun rosters -> returning stages and projections as rosters settle.

### Data caveats

- CFBD defensive stats are sparse before 2016 (~800 rows vs ~6,000/season after), so `def_pct` for the 2015-2016 seasons is unreliable.
- 2020/2021 season pairs are COVID-distorted and excluded from the analysis by default (`--include-covid` to keep them).
- Teams that joined FBS mid-window can have FCS-era rows with tiny stat denominators; the analysis drops shares outside [0,1].
- Transfer classification only sees FBS-to-FBS moves; FCS/JUCO arrivals count as freshmen.

## Make Targets

The included `Makefile` wraps the most common project workflows:

- `make up` / `make down` – start or stop the Docker Compose stack in `infra/docker-compose.yml`.
- `make reset-db` – drop and reapply all Alembic migrations.
- `make teams TEAMS_YEAR=2024` – seed the `teams` table for the requested season.
- `make rosters ROSTER_YEARS="2024 2025" [ROSTER_TEAM="LSU"]` – load rosters for the listed seasons (optionally for a single team).
- `make stats STATS_YEARS="2024 2025" [STATS_TEAM="LSU"]` – load player offense and defense stats.
- `make ret RET_SEASONS="2025" [RET_TEAM="LSU"]` – compute returning production percentages.
- `make inc INC_SEASONS="2025" [INC_TEAM="LSU"]` – compute incoming player mix metrics.
- `make participation` – load `data/participation/*.csv` into `player_participation`.
- `make ol OL_SEASONS="2025" [OL_TEAM="LSU"]` – compute returning OL starts share.
- `make api [API_HOST=0.0.0.0 API_PORT=8000]` – run the FastAPI service with live reloading.

## API

Run `make api` and query the following endpoints:

- `GET /returning/{team_id}/{season}` – offensive, defensive, and overall returning shares from `returning_summary`.
- `GET /incoming/{team_id}/{season}` – transfer share and freshman count from `incoming_summary`.
- `GET /teams` – list teams already loaded into the database.

## Sanity SQL

`sql/sanity_checks.sql` contains helper queries that count player stat rows by season and report LSU's 2025 returning percentages once the ETL has populated `returning_summary`.

## Tests

Run `pytest` to execute the toy SQLite fixtures that validate the returning and incoming metric helpers.
