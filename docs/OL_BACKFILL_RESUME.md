# OL Continuity Backfill — Resume Guide

Handoff doc for finishing the NCAA GP/GS historical scrape that feeds
`ret_ol_starts_share`. Written 2026-08-25. Delete once the backfill and
validation are complete.

## Where things stand

**Pipeline is built and committed** (commit `66ad187`): `player_participation`
table + migration, `etl/load_participation.py`, `etl/compute_ol_continuity.py`,
`db/names.py`, `etl/scrape_ncaa_participation.js`, `tests/test_ol_continuity.py`.
All 42 tests pass.

**Seasons scraped + loaded into `player_participation`:** 2015, 2016, 2018,
2024, 2025 (CSVs in `data/participation/`). Verify with:
```
docker exec infra-db-1 psql -U cfb -d cfb -tc \
  "SELECT season, count(*), count(distinct team_id) FROM player_participation GROUP BY season ORDER BY season;"
```

**Seasons still to scrape:** 2017, 2019, 2020, 2021, 2022, 2023.
(NCAA academic_year = season + 1, e.g. season 2017 lives at academic_year=2018.)

**All CFBD-side data is already staged** for every season 2015–2026: rosters,
team_seasons (SP+), team_outcomes, player stats, returning_summary. So each
newly scraped season computes + validates immediately — no more API backfill
needed.

## The scraping method (important — this is the part that's fiddly)

stats.ncaa.org sits behind Akamai bot protection. Two hard-won rules:

1. **Pace gently, one browser tab only.** Running two tabs in parallel (~4 req/s)
   triggers a multi-hour IP ban. One tab at ~2.5s/request with jitter scraped
   full seasons with zero errors.
2. **Background `fetch()` gets challenged, but real navigations pass.** A full
   page navigation to any `/teams/{id}/roster` URL solves the Akamai JS
   challenge and refreshes the `_abck` cookie. `fetch()` calls made *after* that
   navigation ride on the cleared state and return full pages. So the working
   loop is: **navigate to one roster page to arm → fetch the rest of the season
   in a batch → re-navigate to re-arm if a fetch comes back as a challenge**
   (challenge responses are tiny, <5KB, no `<table>`).

If you get "Access Denied" on a fresh navigation, you're rate-limited: **stop
probing** (each blocked request extends the ban) and wait a few hours. A good
"is it clear yet" test is to open stats.ncaa.org in a normal browser tab — if a
roster loads for you, it's clear.

### Concrete steps per season (driven from Claude-in-Chrome)

1. Create one tab, `navigate` to `https://stats.ncaa.org/teams/449784/roster`
   (any modern roster) to arm. Confirm `document.title === "NCAA Statistics"`
   and `document.querySelectorAll('table tbody tr').length > 0`.
2. In-page, define `__ft` (fetch-with-timeout), `__parseRoster`, and `__runBatch`
   (see the block below), then fetch the season's team list
   `/team/inst_team_list?academic_year=<season+1>&division=11&sport_code=MFB`,
   parse team ids from `a[href^="/teams/"]`, and stash the queue + progress in
   `sessionStorage` (`scQueue`, `scIdx`=0, `scRows`=[], `scErrs`=[]).
3. Fire `window.__runBatch(<queue length>)` — it persists per-team to
   sessionStorage, so tool-call timeouts and blips don't lose progress. Poll
   `sessionStorage.getItem('scIdx')` until it reaches the queue length.
   **Do not close the tab or let the machine sleep** — sessionStorage dies with
   the tab, and an in-flight season is lost (this happened to 2017 once).
4. Filter to starters (`gs > 0`), then transfer out: repeatedly render 256-row
   chunks into `document.body` as `CHUNKSTART\n...\nCHUNKEND` and read them with
   `get_page_text` (the js tool result truncates ~1KB; get_page_text handles
   ~10KB). Paste each chunk to a scratch file.
5. Convert + load:
   ```
   python <scratch>/pipe_to_csv.py <season> <scratch>/sYYYY_all.txt data/participation/<season>.csv
   python -m etl.load_participation --csv data/participation/<season>.csv
   ```
   Rows are `school|player|class|position|gp|gs`. The CSV has header
   `season,school,player_name,class_year,position,gp,gs`. School names resolve
   via `data/school_aliases.csv` (already covers all the NCAA↔CFBD abbreviation
   mismatches from 2015–2025; a brand-new FBS member may need one added).
6. Compute: `python -m etl.compute_ol_continuity --season <season+1>`
   (the metric attaches to the *following* season's returning_detail row).

The batch scraper body lives in `etl/scrape_ncaa_participation.js` (console
version) and the navigate-to-arm variant is described above. `pipe_to_csv.py`
is a 15-line converter — recreate it if the scratch dir is gone:
```python
import csv, sys
season, src, dst = sys.argv[1], sys.argv[2], sys.argv[3]
with open(src) as f, open(dst, "w", newline="") as out:
    w = csv.writer(out); w.writerow(["season","school","player_name","class_year","position","gp","gs"])
    for line in f:
        line = line.strip()
        if not line: continue
        s,n,c,p,gp,gs = line.split("|")
        w.writerow([season,s,n,c,p,int(gp),int(gs)])
```

## Sanity checks

- Per-team OL starts should be ≈ 5 × games played (e.g. a 13-game team ~55–75
  total OL starts). Low outliers (~49) are fine for teams that rotated.
- Name-match diagnostic: of one season's OL starters, ~90%+ of Fr/So/Jr should
  appear on the next season's CFBD roster, ~30% of Sr (they graduate). Big
  deviations mean the name join is broken.

## Final step once all seasons are loaded

Run the validation and decide whether the feature earns model weight:
```
python -m etl.compute_ol_continuity                 # all seasons
python -m analysis.validate_ol_continuity           # 2016-2025, COVID excluded
```
The incremental OLS in that script is the decision gate: does
`ret_ol_starts_share` add signal *beyond* `overall_pct`? Early read on 2016–2017
only: +4.7 SP+ per unit share, positive R² gain — promising but n=2 seasons, not
yet significant. Need the full panel. Only if it holds should it enter
`model/` projections (respect the `db/weights.py` rule: features must beat the
baseline before adoption).
```
