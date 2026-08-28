# CFB Returning Production

Talent retention in college football's transfer-portal era, measured and modeled. Starting from Bill Connelly's "returning production," this project (1) shows the raw stat is measuring less every year as rosters turn over, (2) builds a portal-adjusted version that credits incoming transfers at tier-translated value, (3) adds offensive-line continuity from scraped NCAA games-started data, and (4) feeds all of it into a preseason win-projection model that is backtested leak-free against sportsbook win totals: 57.8% lean hit rate (241/417, p=.002) and lower error than the posted totals themselves (MAE 1.72 vs 1.76). The 2026 projections are frozen in `writing/projections_2026.csv`; the write-up and figures are in `writing/`.

Under the hood: an ETL layer that loads CollegeFootballData rosters and stats into Postgres, computes returning and incoming production summaries, and a validation harness that tests every feature before it enters the model.

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

**Validation** (`analysis/validate_ol_continuity.py`, COVID seasons excluded). On
2016–2024 pairs (n=907) returning OL starts share added **+5.1 SP+ per unit share
beyond `overall_pct`** (season-clustered bootstrap p<.001, 95% CI [+2.7, +8.0]).
With the 2025 pairs added (n=1041, eight seasons) that plain gate reads +3.1
(p=.075): 2025 is the first negative season of the eight (OL slope −3.5 on its own,
with the mean returning share at a record-low .43 as portal churn hit the position)
— one noisy season, not a reversal. The gate that matters is `--full-spec`, which
runs the same incremental test inside the production rating spec: **+3.6 SP+ per
unit share beyond prior SP+ and the split continuity indexes** (season-clustered
bootstrap p<.001, 95% CI [+1.2, +6.3], n=1044). Teams returning <25% of OL starts
averaged −3.4 SP+ / −0.64 wins; 75%+ averaged +1.0 SP+ / +0.40 wins.
`player_participation` covers seasons 2015–2025 (`data/participation/`), so the
metric exists for 2016–2026.

**In the model (v3, `MODEL_VERSION = "v3-ols-ol-continuity"`).** The share enters
`model/rating.py` as `continuity_ol`, a separate additive term rather than a blend
into offensive continuity: it is nearly orthogonal to prior SP+ (r=.01) and only
weakly related to the yards-based offensive share (r=.19), and a fixed
Connelly-style blend at the data-implied weight (~⅓ of the offensive-continuity
weight) fits no better than letting OLS weight it. It sits in both the model and
the raw-returning baseline so the portal-adjustment head-to-head stays clean;
`NO_OL_FEATURES` is the ablation spec the backtest scores it against
(`model_no_ol`), alongside an OL-divergence subset (teams whose OL continuity most
disagrees with their skill-position continuity, where the term can actually move
a lean). Missing shares (3–6 teams a season) are imputed at the season mean so the
training rows match the no-OL spec exactly. The expanding-window OL coefficient
runs +3.3 (2019 fold, p=.05) → +5.1 (2025 fold) → **+2.7 in the production 2026
fit (p=.012, n=1,116, with recruiting and coaching controls)**; the season-clustered
bootstrap on the same spec gives +2.8 (p=.073, CI [−0.3, +6.0]) — conservative with
eight season clusters and 2025 negative. **Backtest ablation** (identical folds,
games, calibration, translation): pooled MAE 1.688 with OL vs 1.694 without (better
in 4 of 5 folds; 2025 the exception), market hit rate **57.8% vs 56.1%** (241 vs
234 of 417), portal-divergence subset 61.3% vs 56.2%. On the OL-divergence subset
both variants hit 65.5% (57/87) against the raw-returning model's 58.6% — the OL
term earns its keep in the overall and portal-divergence numbers, not on that
subset. v3 is the production spec.

## Win projections (2026-08 milestone)

```
python -m model.run_projections --season 2026      # fit, simulate, store win_projections
python -m analysis.backtest_win_projections        # time-safe backtest vs baselines + market
python -m analysis.divergence_board                # the portal divergence board
```

The model predicts each team's SP+ rating from preseason-knowable features (v2 fit: prior SP+ .61, portal-adjusted offensive continuity +11.0, defensive continuity +1.9 (p=.02), new head coach -1.8, recruiting z +3.3; v3 adds OL continuity — see "Offensive line continuity" above). Continuity enters as separate fitted offense/defense features — the old blended index gave offense ~90% weight by the accident of yards-vs-tackles units; the fitted balance lands near 85/15, so the accident was close to right, but now it's a measurement instead of a coincidence. The model converts rating gaps to per-game win probabilities (logistic on 7,769 games: .128/SP+ point, home field +.30; FCS opponents get a rating-conditioned curve — ~86% for bottom-tier teams to 99.7% for elite, replacing a flat 93.7% that treated Alabama and a 2-win G5 team identically), applies Platt recalibration (gamma=.66, fixes tail overconfidence from predicted-rating noise), and sums exact Poisson-binomial win distributions over the real schedule (conference championship games excluded — their matchups encode season outcomes and book totals exclude them; see `model.simulate.drop_ccgs`).

**Backtest (v3; 2019, 2022-2025, everything fit strictly pre-season — rating model, win curve, FCS curve, Platt calibration, and transfer-translation coefficients are all re-derived per fold from prior seasons only; CCGs excluded throughout):** MAE 1.69 wins vs 1.69 (same spec without the OL term), 1.70 (raw-returning baseline) and 1.83 (carry-forward); **57.8% against market win totals (241/417, program-clustered bootstrap p=.002, 95% CI .531-.624)** vs 56.1% without OL and 54.9% for the raw-returning baseline. On the portal-divergence subset the model hits **61.3% vs 53.7%** for an otherwise-identical raw-returning model (56.2% without OL) — the portal adjustment earns its edge where published returning production is most wrong, though n=80 keeps that split directional. On identical market-covered team-seasons the model's MAE (1.72) edges the posted totals' own MAE (1.76), winning 3 of 5 seasons — market-grade accuracy from a free-data pipeline. (v2, before the OL term and on a data snapshot through 2024: MAE 1.69, 55.6% (232/417, p=.037), divergence subset 56.2% vs 50.0%.) The fold-safe translation coefficients drift across windows (offensive G5→P4 from ~0.86 on 2021-only data to ~0.64 by 2025) yet the results hold, so the adjustment's value doesn't depend on knowing the mature coefficients in advance. (Earlier drafts quoted 58.1%/p=.001; that figure leaked CCG outcomes into the schedule, pooled Platt calibration across eval folds, used translation coefficients estimated through 2025 in earlier folds, and tested with an IID binomial — all corrected here.)

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
- CFBD enforces a **monthly call quota** (`429 Monthly call quota exceeded`, header `x-calllimit-remaining`). A full `etl.backfill` is ~60 bulk calls, but the `coaches` stage is one call per team (~137), so budget it. Before fitting or backtesting, check that `recruiting`, `coach_changes`, `games`, `game_lines`, and `win_totals` are populated — `build_features` yields NaN `recruit_z` when `recruiting` is empty and the training set silently collapses to zero rows.

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
