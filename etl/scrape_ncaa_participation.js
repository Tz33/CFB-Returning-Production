// etl/scrape_ncaa_participation.js
//
// Collects per-player GP/GS rows for every FBS team from stats.ncaa.org
// roster pages. The site sits behind bot protection that blocks plain HTTP
// clients, so this runs inside a real browser session instead of Python:
// open https://stats.ncaa.org/team/inst_team_list?academic_year=<YYYY>&division=11&sport_code=MFB
// (academic_year 2025 = fall 2024 season), paste this file into the DevTools
// console, then call:
//
//   await scrapeParticipation()          // all teams on the open list page
//
// Progress logs to the console. When it finishes it prints pipe-delimited
// rows (school|player|class|position|gp|gs) filtered to OL positions; feed
// them to data/participation/<season>.csv (columns:
// season,school,player_name,class_year,position,gp,gs) and load with
// `python -m etl.load_participation`. Adjust POSITIONS to collect more.
//
// Please keep the per-request delay — ~135 sequential requests once a year
// is polite traffic; hammering the site is not.
//
// Operational notes (learned scraping 2015-2025, Aug 2026):
// - Akamai bot protection. ONE tab, sequential requests, ~2.5s + jitter apart.
//   Two tabs in parallel, or a stray extra request while a batch is running,
//   earned multi-hour IP bans. A 403 "Access Denied" page IS the ban — stop
//   probing (every blocked request extends it) and wait a few hours.
// - Background fetch() can get the JS challenge (HTTP 200, <5KB, no <table>),
//   but a real page navigation to any /teams/<id>/roster passes and refreshes
//   the cookie; fetches made afterwards ride on it. Loop: navigate to arm ->
//   fetch the season -> re-navigate if a response looks like a challenge.
// - Persist progress per team (sessionStorage survives navigation; closing
//   the tab loses it) so a blip doesn't cost the whole season.
// - Chrome throttles setTimeout in hidden tabs; if the tab won't stay visible,
//   drive the delay from a Web Worker timer instead.
// - Sanity checks: every FBS team should appear with ~5 x games-played OL
//   starts (48-78 for a full season; ~0 only for COVID opt-outs in 2020).
// - The site lists a few teams' linemen as OT/OG/C rather than OL;
//   etl/compute_ol_continuity.py accepts all of them.

const POSITIONS = ['OL', 'OT', 'OG', 'OC', 'C', 'G', 'T'];
const DELAY_MS = 2500;

function parseRoster(html, school) {
  const doc = new DOMParser().parseFromString(html, 'text/html');
  const out = [];
  for (const table of doc.querySelectorAll('table')) {
    const headers = [...table.querySelectorAll('thead tr:first-child th')]
      .map(th => th.textContent.trim());
    const gp = headers.indexOf('GP'), gs = headers.indexOf('GS');
    const nm = headers.indexOf('Name'), cl = headers.indexOf('Class'),
          ps = headers.indexOf('Position');
    if (gp < 0 || gs < 0 || nm < 0) continue;
    for (const tr of table.querySelectorAll('tbody tr')) {
      const td = [...tr.querySelectorAll('td')].map(x => x.textContent.trim());
      if (td.length < headers.length) continue;
      const pos = ps >= 0 ? td[ps].toUpperCase() : '';
      if (!POSITIONS.includes(pos)) continue;
      out.push([school, td[nm], cl >= 0 ? td[cl] : '', pos,
                parseInt(td[gp]) || 0, parseInt(td[gs]) || 0].join('|'));
    }
    break; // first matching table is the roster grid
  }
  return out;
}

async function scrapeParticipation() {
  const teams = new Map();
  document.querySelectorAll('a[href^="/teams/"]').forEach(a => {
    const m = a.getAttribute('href').match(/^\/teams\/(\d+)$/);
    const t = a.textContent.trim();
    if (m && t) teams.set(m[1], t);
  });
  console.log(`${teams.size} teams`);

  const rows = [], errs = [];
  let i = 0;
  for (const [id, school] of teams) {
    try {
      const r = await fetch(`/teams/${id}/roster`, { credentials: 'include' });
      if (!r.ok) { errs.push(`${school}:${r.status}`); continue; }
      const parsed = parseRoster(await r.text(), school);
      if (!parsed.length) errs.push(`${school}:0rows`);
      rows.push(...parsed);
    } catch (e) { errs.push(`${school}:${e.message}`); }
    if (++i % 10 === 0) console.log(`${i}/${teams.size}, rows=${rows.length}`);
    await new Promise(res => setTimeout(res, DELAY_MS));
  }
  if (errs.length) console.warn('errors:', errs);
  console.log(rows.join('\n'));
  return rows;
}
