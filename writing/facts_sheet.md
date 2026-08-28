# Facts sheet — every number in the draft, with provenance

All numbers regenerated 2026-08-26 from the local Postgres (`infra/docker-compose.yml`) with the DB fully loaded 2014–2026. Rerun the listed command to reproduce. Model version `v3-ols-ol-continuity`.

## Retention trend (Figure 1)
Source: SQL over `returning_summary` / `returning_detail` (see `writing/figures` script; `python -m analysis.validate_returning_production` for the merged frame).

| season | n | mean raw returning | mean portal-adjusted | mean OL starts share | share of teams <40% raw |
|---|---|---|---|---|---|
| 2015 | 133 | .625 | — | — | .150 |
| 2016 | 133 | .641 | — | .578 | .150 |
| 2017 | 133 | .608 | — | .592 | .173 |
| 2018 | 134 | .602 | — | .639 | .164 |
| 2019 | 134 | .599 | — | .588 | .157 |
| 2020 | 131 | .619 | — | .647 | .153 |
| 2021 | 129 | .716 | .849 | .748 | .054 |
| 2022 | 135 | .570 | .700 | .588 | .230 |
| 2023 | 137 | .543 | .689 | .561 | .270 |
| 2024 | 137 | .480 | .675 | .529 | .380 |
| 2025 | 137 | .394 | .594 | .433 | .526 |
| 2026 | 136 | .388 | .589 | .384 | .537 |

Note: 2015–16 defensive stats are sparse in CFBD (README caveat), so `mean_def` for those years is not quoted.

## Does returning production matter (Figure 2)
`python -m analysis.validate_returning_production` — 2015–2025, COVID pairs excluded, n=1,212.
- overall_pct vs ΔSP+: r=.261 (n=1,168); vs Δwins r=.194.
- off_pct vs ΔSP+ r=.254; def_pct r=.071. Weighted defense lifts def to r=.21 (README, `analysis/validate_weighted_returning.py`).
- Buckets (n / mean Δwins / mean ΔSP+): <40% 297 / −0.73 / −3.01; 40–60% 353 / −0.13 / −0.78; 60–80% 394 / +0.29 / +0.67; 80%+ 168 / +1.06 / +3.82.
- Category weights reproduce Connelly ordering (receiving .42 > passing .33 > rushing .25): `analysis/estimate_category_weights.py`.
- Market spreads already price raw returning production: 52.8% on extreme quintiles, p=.14 (`analysis/validate_market_spreads.py`, README).

## Portal adjustment (Figure 5)
- Raw metric 2022–2025: r=.157; portal-adjusted: r=.254; Steiger p=.004 (`analysis/validate_adjusted_returning.py`, README).
- Translation coefficients (`db/translation.py`; `analysis/estimate_transfer_translation.py`, dest seasons 2021–2025): offense G→P .583, P→G 1.48, G→G .944, P→P 1.056 (n=1,255, total_yards ≥100); defense G→P .642, P→G 1.534, G→G .957, P→P .969 (n=1,573, tackles ≥10). Total movers 2,828. Zero-production destinations included.
- Teams above 100% adjusted continuity averaged +1.9 wins (README).
- 2026 largest raw→adjusted gaps (`python -m analysis.divergence_board --season 2026`): Oklahoma State .022→1.161, Penn State .080→.947, Auburn .204→1.041, Wisconsin .374→1.165, LSU .234→.987, Iowa State .043→.685, Virginia .158→.791, Miami .441→1.021, Indiana .170→.677, Texas .620→1.112.

## OL continuity
`python -m analysis.validate_ol_continuity [--full-spec]` (README "Offensive line continuity").
- Data: stats.ncaa.org GP/GS, seasons 2015–2025 → `player_participation`; feature = returning share of prior-season OL games started.
- Buckets: <25% OL starts −3.4 SP+ / −0.64 wins; 75%+ +1.0 SP+ / +0.40 wins.
- Plain gate through 2024 (n=907): +5.1 SP+/unit, p<.001. With 2025 (n=1,041): +3.1, p=.075 — 2025 first negative season of eight.
- Full-spec (inside the rating model): +3.6, season-clustered bootstrap p<.001, CI [+1.2, +6.3], n=1,044.
- Production 2026 fit coefficient: +2.75, p=.012 (n=1,116). Season-clustered bootstrap on same spec: +2.81, p=.073, CI [−0.3, +6.0].
- Mean OL share: 2025 .433 (record low at the time), 2026 .384.
- Ablation (backtest): pooled MAE 1.688 with OL vs 1.694 without; hit rate 57.8% vs 56.1%; better in 4 of 5 folds (2025 the exception).

## Rating model (production 2026 fit, n=1,116)
`python -m model.run_projections --season 2026` prints this table.

| feature | beta | p |
|---|---|---|
| intercept | −8.120 | <.001 |
| sp_prev | 0.612 | <.001 |
| continuity_off | 10.635 | <.001 |
| continuity_def | 1.633 | .045 |
| continuity_ol | 2.747 | .012 |
| new_head_coach | −1.646 | .002 |
| recruit_z | 3.255 | <.001 |
| portal_era | −0.738 | .136 |
| is_new_fbs | 5.378 | .069 |

Win curve: logistic on 7,769 games, .128/SP+ point, home field +.30; FCS rating-conditioned curve; Platt γ=.66; exact Poisson-binomial over real schedule; CCGs dropped (`model/game_prob.py`, `model/simulate.py`). New-coach raw effect: −1.1 SP+ vs +0.3 under continuity (`analysis/validate_coaching_interaction.py`).

## Backtest (Figure 3)
`python -m analysis.backtest_win_projections` (rerun 2026-08-26; output matched README exactly).
- MAE by season (model / market / raw-returning / carry-forward): 2019 1.616 / — / 1.616 / 1.798; 2022 1.561 / — / 1.596 / 1.784; 2023 1.597 / — / 1.594 / 1.771; 2024 1.771 / — / 1.776 / 1.923; 2025 1.895 / — / 1.900 / 1.879. Pooled: model 1.688, no-OL 1.694, raw-returning 1.696, carry 1.831.
- Market-covered team-seasons only (n=436): model 1.724 vs market 1.757. By season model/market: 2019 1.732/1.747; 2022 1.561/1.700; 2023 1.542/1.442; 2024 1.732/1.877; 2025 1.908/1.898. Model wins 3 of 5.
- Hit rate vs posted totals: model 241/417 = 57.8% (program-clustered bootstrap p=.002, CI .531–.624); no-OL 234/417 = 56.1%; raw-returning 229/417 = 54.9% (p=.067).
- By season (model): 2019 41/81 (50.6%); 2022 48/74 (64.9%); 2023 33/65 (50.8%); 2024 42/64 (65.6%); 2025 77/133 (57.9%).
- Divergence subset (2022–2025, n=80): model 49/80 = 61.3% (cluster p=.039, CI .507–.716); no-OL 45/80 = 56.2%; raw-returning 43/80 = 53.7%.
- OL-divergence subset (n=87): 65.5% for both model and no-OL; raw-returning 58.6%.
- Calibration (pooled): P(≥6 wins) buckets predicted→realized: 0–25% .121→.248; 25–50% .367→.340; 50–75% .634→.627; 75–100% .913→.820. P(≥8): .083→.181; .369→.314; .628→.581; .869→.840.
- Fold-safe translation drift: offense G→P 0.858 (2022 fold) → 0.800 → 0.724 → 0.636 (2025 fold) → 0.583 production.
- Leak history (README): earlier draft 58.1%, p=.001 — leaked CCG outcomes, pooled Platt across folds, translation coefficients through 2025 in early folds, IID binomial test. All corrected → 57.8%, p=.002.

## 2026 projections (Figure 4; `writing/projections_2026.csv`)
`win_projections` table, season 2026, model v3, stored 2026-08-26. Totals: BetMGM via Yahoo, added 2026-08-10 (`data/win_totals.csv`), 136 rows; Rutgers has no matched total (135 leans).
- Leans: 76 over, 59 under; mean edge +0.044 wins; mean xW 6.40 vs mean total 6.35. |edge|≥1: 29; ≥1.5: 9; ≥2: 4.
- Top rating_pred: Ohio State 29.49, Oregon 27.15, Georgia 24.84, Miami 23.10, Texas 22.98, Indiana 22.93, Texas Tech 22.61, Notre Dame 22.39, USC 21.01, Texas A&M 20.78.
- Top expected wins: Texas Tech 10.66, Miami 10.14, Notre Dame 10.07, Oregon 9.64, Georgia 9.47, Ohio State 9.43, Utah 9.41, Indiana 9.17.
- Largest overs (xW vs total): Iowa State 6.63/4.5 (+2.13), Vanderbilt 7.20/5.5, Louisiana Tech 7.15/5.5, UConn 7.13/5.5, Tulsa 6.99/5.5, San Diego State 7.95/6.5, Northern Illinois 4.88/3.5, Southern Miss 4.83/3.5, Nevada 5.81/4.5, North Texas 6.69/5.5.
- Largest unders: Army 4.92/7.5 (−2.58), Oklahoma State 4.21/6.5, UCLA 4.42/6.5, Florida 5.51/7.5, Navy 5.82/7.5, Notre Dame 10.07/11.5, Alabama 7.15/8.5, Indiana 9.17/10.5, Michigan 7.20/8.5, Louisville 7.26/8.5.
- Rating decompositions (intercept −8.12 plus terms):
  - Army: sp_prev +0.5, off +6.2, def +0.5, OL +2.1, recruit_z −12.3 (z=−3.80, FBS minimum; recruit_points 39.85) → −11.9.
  - Navy: recruit_z −7.8 (z=−2.39) → −8.4. Air Force: recruit_z −6.5 → −8.4.
  - Vanderbilt: sp_prev +12.4 (from 20.3), off +4.2, recruit +1.9 → 11.5.
  - Iowa State: sp_prev +6.1 (from 9.9), off +7.5 (adj .685), OL +0.0 (share 0), new coach −1.6 → 4.0.
  - Oklahoma State: sp_prev −9.2 (from −15.1), off +13.1 (adj 1.161), new coach −1.6 → −6.1.
  - Indiana: sp_prev +19.8 (from 32.4), off +7.2, recruit +2.0 → 22.9.
- Grading math: 135 leans × .578 = 78.0 expected hits; binomial SD √(135×.578×.422) = 5.7; chance = 67.5.

## Pre-publish checklist
1. Rosters are August snapshots. Right before posting: `python -m etl.backfill --start-year 2026 --end-year 2026 --only rosters,returning,incoming` (then `make ol OL_SEASONS=2026` is a no-op until 2026 NCAA data exists), then `python -m model.run_projections --season 2026` and regenerate `writing/projections_2026.csv` + figures 4/5. Budget: ~3 CFBD calls.
2. Re-check BetMGM totals (they move in late August); update `data/win_totals.csv`, `python -m etl.load_win_totals`.
3. Verify the `new_head_coach` flags the post leans on (Iowa State, Oklahoma State, Penn State, LSU, UCLA, Florida, Michigan, UConn, North Texas, Northern Illinois) against reality — they come from CFBD `/coaches`.
4. `git add writing/ && git commit -m "Freeze 2026 projections"` — cite the short SHA in the post as the timestamp. Push so the hash is public.
5. Fill the `[[...]]` placeholders: date, repo link, personal intro.
6. Decide whether to name the service-academy blind spot in the post (currently included — recommended; it's the most credible paragraph in there).
