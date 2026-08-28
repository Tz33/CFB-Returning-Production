# I spent a year trying to fix "returning production." Here's what the model says about 2026.

*Every number below comes from a public dataset and a pipeline anyone can rerun. The predictions are frozen before Week 1. I'll grade them in December, in public, whether they hold up or not.*

---

## Why I did this

Every August you see the same stat: "Team X returns 71% of its production." It's on broadcasts, in preview magazines, in every win-total writeup. It's a good stat. Bill Connelly built it, and it works — I checked, and I'll show you.

But the thing it measures is disappearing.

[FIGURE: fig1_retention_collapse.png]

In 2015, the average FBS team returned about 63% of its prior-season production. In 2026 it's 39%. In 2015, roughly one team in seven returned less than 40%. This year it's more than half of FBS.

That's the transfer portal. And it creates a specific problem: "returning production" counts the players who *stayed*. It says nothing about the players who *arrived*. When Oklahoma State returns 2% of its production but signs a full roster out of the portal, the number everyone quotes says "empty cupboard," and it's wrong — or at least, it's answering a question nobody is asking anymore.

I wanted to know three things:

1. Does returning production actually predict anything? (Yes.)
2. Can you fix it for the portal era? (Mostly.)
3. Is there anything the stat-based version can't see at all? (The offensive line.)

Then I built a win-projection model from it, backtested it honestly against the betting market, and I'm putting the 2026 numbers here before the season so nobody — including me — can move the goalposts.

[[Optional: one or two sentences on who you are and why you started this — the more specific the better. "I'm not a professional; I did this at night with a Postgres database and a $0 API key" is more credible than any credential.]]

---

## Part 1: Yes, it matters

I pulled player-level stats for every FBS team from 2014 through 2025 from [CollegeFootballData](https://collegefootballdata.com), matched each August roster against the prior season's box scores, and computed the share of prior-year production (passing, rushing, receiving yards on offense; tackles, TFLs, interceptions and the rest on defense) that was still on the roster.

Then I asked the obvious question: do teams that return more, improve more?

[FIGURE: fig2_buckets.png]

They do. Across 1,212 team-seasons (2015–2025, throwing out the COVID-eligibility years), teams that returned under 40% of their production got worse by about three-quarters of a win and three SP+ points on average. Teams returning 80%+ improved by about a win and nearly four SP+ points. The correlation between returning production and year-over-year SP+ change is r = .26 — not huge, but real, monotonic, and stable.

Two details that matter later:

- **Almost all of the signal is on offense.** Offensive returning production correlates with improvement at r = .25; defensive at r = .07. That's mostly a measurement problem — "tackles" is a bad proxy for defensive value. Reweighting defensive categories toward tackles-for-loss and interceptions lifts the defensive number to r = .21. When I fit the weights on offense, the data reproduced Connelly's ordering on its own (receiving > passing > rushing), which was a nice sanity check that I wasn't measuring noise.
- **The betting market already knows this.** I checked whether early-season point spreads were systematically off for high- or low-retention teams. They weren't (52.8% on the extreme quintiles, not significant). So the raw stat isn't an edge. If there's an edge, it has to come from doing something the published number doesn't.

---

## Part 2: Fixing it for the portal

Here's where the raw stat breaks. Restricting to the portal era (2022–2025), the correlation between raw returning production and improvement fell to r = .16. The stat was losing its grip because it only sees half the roster movement.

The fix is conceptually simple: **credit incoming transfers for their prior production, discounted for where they came from.** A 1,000-yard receiver moving from the MAC to the SEC shouldn't count as 1,000 yards.

How much to discount? I didn't guess. I tracked 2,828 portal-era players with meaningful production who showed up on a different FBS roster the next year — including the ones who produced *nothing* at their new school, because leaving those out would be cheating — and measured what fraction of their production actually carried over:

| Move | Offense | Defense |
|---|---|---|
| Group of Five → Power Four | 0.58 | 0.64 |
| Power Four → Group of Five | 1.48 | 1.53 |
| Same tier | ~1.0 | ~1.0 |

So a G5 player moving up keeps roughly 60% of their production; a P4 player moving down gets about 50% more. Neither number is surprising, but now it's measured instead of assumed.

Adding translated incoming production to the returning number gives a **portal-adjusted continuity index**. In 2022–2025, it restores the correlation with improvement to r = .25 — basically back to where the raw stat was before the portal (the difference is statistically significant, p = .004). Teams above 100% adjusted continuity — meaning they brought in more production than they lost — averaged +1.9 wins.

Here's what the two numbers look like side by side for 2026:

[FIGURE: fig5_raw_vs_adjusted.png]

Every dot above the diagonal is a team the raw stat undersells. Oklahoma State, Penn State, Auburn, Wisconsin, LSU, Iowa State: these are the teams where the number on the broadcast graphic and the number in my database disagree by 60 to 110 percentage points. Whether that disagreement means the *market* is wrong about them is a separate question — I'll get to it.

---

## Part 3: The thing nobody measures

There's one position group that every stat-based returning metric ignores completely: the offensive line. Linemen don't accumulate box-score stats. Connelly's version handles this with a career-starts term; the public API I use has no snap counts, no participation data, nothing.

So I went and got it. The NCAA's own stats site lists games played and games started for every player on every roster, going back more than a decade. I scraped it — all of FBS, 2015 through 2025 — and built a single number: **the share of last season's offensive-line starts that are back on this year's roster.**

It's a starts share, not a yards share, so I kept it as its own feature rather than blending it into the offensive number. And I made it pass the same test as everything else: does it predict improvement *beyond* what returning production and prior rating already explain?

It does. Teams returning less than 25% of their OL starts averaged −3.4 SP+ and −0.64 wins; teams returning 75%+ averaged +1.0 SP+ and +0.40 wins. In the full model, each unit of OL continuity is worth about 2.7 SP+ points over and above everything else (p = .012 on 1,116 team-seasons).

**Honest caveat:** 2025 was the first season out of eight where the OL effect went the wrong way. The average returning OL share hit a record low that year (43%) and it's lower again in 2026 (38%) — the portal has reached the trenches. A more conservative test that treats each season as one observation gives p = .07 rather than .01. I think the effect is real, the ablation below agrees, but I want you to know that one of the eight seasons disagrees.

---

## The model

The rating model is deliberately boring: ordinary least squares, predicting each team's end-of-season SP+ from things you can know in August.

| Feature | Effect on SP+ |
|---|---|
| Last year's SP+ | ×0.61 (a good team regresses ~40% toward the pack) |
| Portal-adjusted offensive continuity | +10.6 per unit |
| Portal-adjusted defensive continuity | +1.6 per unit |
| Returning OL starts share | +2.7 per unit |
| New head coach | −1.6 |
| Recruiting (z-score within season) | +3.3 per SD |

Then: convert each team's projected rating into a win probability for every game on its real schedule (about 0.128 per SP+ point, +0.30 for home field, fit on 7,769 games), recalibrate to fix the overconfidence that comes from a noisy rating, and sum an exact win distribution. Conference championship games are excluded because sportsbook totals exclude them.

That's it. No injury data, no quarterback-specific term, no transfer *quality* beyond production. There's a lot this model doesn't know. That's part of the point — I wanted to know what the roster-continuity signal alone is worth.

---

## The backtest, and the part where I almost fooled myself

A backtest is only worth anything if it can't peek. So for each test season (2019, 2022, 2023, 2024, 2025), *everything* was re-fit using only prior seasons: the rating model, the win-probability curve, the calibration, even the transfer-translation coefficients above. In the 2022 fold the model only had one season of portal data to learn from, and the G5→P4 coefficient it came up with was 0.86, not 0.58. It didn't matter much. The results held anyway, which is the thing I actually care about — the adjustment works even when you don't know the mature coefficients yet.

[FIGURE: fig3_backtest.png]

Scored against the preseason win totals posted by sportsbooks:

- **The model's lean beat the posted total 57.8% of the time** (241 of 417 team-seasons, 95% CI 53–62%). A model that only used raw returning production hit 54.9% on the same teams.
- **On the "portal divergence" subset** — the 20% of teams each year where raw and adjusted continuity disagree most — the model hit **61.3%** vs 53.7% for the raw-returning version. That's exactly where the adjustment should matter, and it's where it does. But it's n = 80, so treat it as directional.
- **Mean absolute error of 1.72 wins vs the market's own 1.76** on identical teams. The model beat the books' number in three of five seasons and lost narrowly in the other two. That's a free-data pipeline being market-grade. I did not expect that.

Now the uncomfortable part. Look at the right-hand chart. Two of the five seasons were coin flips (51%). The pooled number is good; the season-by-season numbers are streaky. If 2026 comes in at 51%, that is *consistent with the backtest*, not a refutation of it. And if it comes in at 66%, that's consistent too. One season can't settle this. I'll say more about scoring below.

And the part I'm least proud of: an earlier version of this backtest said 58.1% with p = .001. When I went looking for leaks, I found three. The schedule included conference championship games, whose *existence* encodes how the season went. The calibration step was fit on all test seasons at once. And the significance test treated every team-season as independent, when the same programs show up five times. Fixing all three moved the number from 58.1% to 57.8% — trivially — but the p-value went from .001 to .002, and the "divergence subset" claim got noticeably weaker. I'm telling you this because the difference between a real result and a fake one is usually not in the headline number. It's in whether you went looking.

---

## What it says about 2026

Frozen as of [[DATE]], rosters as of the August snapshot, totals from BetMGM. The full table of all 136 teams is [linked at the bottom](#the-full-table).

**Top of the ratings:** Ohio State (29.5), Oregon (27.2), Georgia (24.8), Miami (23.1), Texas (23.0), Indiana (22.9), Texas Tech (22.6), Notre Dame (22.4). Highest expected win totals: Texas Tech 10.7, Miami 10.1, Notre Dame 10.1, Oregon 9.6.

**Where it disagrees with the market:**

[FIGURE: fig4_2026_leans.png]

Across 135 teams with a posted total, the model leans over on 76 and under on 59, and the average disagreement is basically zero (+0.04 wins) — it's not systematically higher or lower than the books, it just disagrees about *which* teams. Twenty-nine leans are a full win or more; four are two wins or more.

A few I find interesting, and a few I don't trust:

**Iowa State over 4.5 (model: 6.6).** The rawest example of the whole thesis. Iowa State returns 4% of its production — the second-lowest number in FBS — and has a new head coach. On the broadcast graphic this is a teardown. But the portal reload takes adjusted continuity to 68%, and the model still sees a team coming off a +9.9 SP+ season. The biggest over lean on the board.

**Vanderbilt over 5.5 (model: 7.2).** Vandy was a +20 SP+ team last year. The model regresses that hard (to +11.5) and still gets to seven wins on the schedule. The market is pricing a bigger collapse than a regression-plus-continuity model can justify.

**Oklahoma State under 6.5 (model: 4.2).** This one's important because it cuts *against* the portal narrative. Oklahoma State has the largest raw-vs-adjusted gap in the country: 2% returning, 116% adjusted. The portal reload is real, and it's worth +13 SP+ in the model. But the team it's reloading was −15 SP+ last year with a new coach on top, and that's a deeper hole than a good portal class fills. The adjustment says "not as bad as 2% implies," not "good."

**Penn State under 8.5 (model: 7.7)** and **LSU under 8.5 (model: 7.5)** are the same shape: huge portal reloads (8% → 95%, 23% → 99%), new coaches, and the model lands a win short of the number. These are close; I'd call them leans, not convictions.

**Indiana under 10.5 (model: 9.2)** and **Notre Dame under 11.5 (model: 10.1)** are regression calls. Indiana was the best team in the country by SP+ last year (+32) and returns 17% of its production. The model still has them as a top-six team; it just doesn't have them at 10.5 wins.

**Army under 7.5 and Navy under 7.5 — don't trust these.** I want to flag the model's worst blind spot myself. The recruiting term uses composite class rankings, and service academies don't recruit that way. Army's recruiting z-score is −3.8, the lowest in FBS, and that single term subtracts 12 SP+ points from its rating. Everything else about Army's profile (55% returning, 77% of OL starts back, no coaching change) is fine. The model is wrong about how service academies work, and I'm not going to pretend the under is a real lean. Same logic for Navy and Air Force. If I fix one thing before next year, it's this.

**UCLA under 6.5 (model: 4.4), Florida under 7.5 (model: 5.5), Michigan under 8.5 (model: 7.2)** are all new-coach teams where the market seems to be pricing a clean reset and the model is pricing a −1.6 SP+ transition cost on top of whatever the roster says.

---

## How I'll grade this

In December I'll publish:

1. **Hit rate of every lean against the BetMGM totals** in the table below, over/under, no cherry-picking, ties excluded. The backtest says to expect around 58%. With 135 leans, 58% means about 78 hits; pure chance is 67 or 68, with a standard deviation of about 6. So anything from ~70 to ~86 is "consistent with the backtest," which is a wide band, which is the honest answer about what one season can tell you.
2. **Mean absolute error vs actual wins**, model and market side by side. Backtest says ~1.7 for both, with the model slightly better.
3. **The portal-divergence subset** (the 27 teams with the biggest raw-vs-adjusted gap) separately, because that's where the thesis actually lives.
4. **The Army/Navy/Air Force results**, because if I'm going to flag a blind spot in advance I should report how it went.

What would make me change my mind: a hit rate below 50% on the full board would be the first losing season in six, and I'd take that seriously. A bad season on the divergence subset specifically would hurt more, because that's the part that isn't just "prior rating plus regression."

What *wouldn't* change my mind: a 52% season. That happened twice in the backtest. It's noise. The claim was never "this beats the books every year." It's "the stat everyone quotes is measuring less and less each year, here's a version that measures more, and here's the evidence it's worth about 3 to 4 points of hit rate over a five-year window."

---

## The full table

[[Link to `projections_2026.csv` — GitHub raw link or Substack attachment. Commit it and cite the commit hash here as the timestamp: "frozen at commit `abc1234`".]]

Columns: last year's SP+, projected SP+, expected wins, BetMGM total, the lean, probability of reaching 6/8/10 wins, and the three continuity numbers (raw, portal-adjusted, OL starts share).

## Data and code

- Player stats, rosters, SP+, schedules, recruiting: [CollegeFootballData](https://collegefootballdata.com) (free tier).
- Games played / games started, for the OL feature: [stats.ncaa.org](https://stats.ncaa.org) roster pages, 2015–2025.
- Preseason win totals: BetMGM (2026, via Yahoo); various books 2018–2025 for the backtest.
- Code: [[repo link]]. Everything — the ETL, the translation estimates, the model, the leakage-safe backtest — is in there. If you find a leak I missed, I genuinely want to know.

*Nothing here is betting advice. The model is a roster-continuity signal with a backtest; it doesn't know who your quarterback is.*
