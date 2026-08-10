-- Total rows in player_stats_offense grouped by season
SELECT season,
       COUNT(*) AS row_count
FROM player_stats_offense
GROUP BY season
ORDER BY season;

-- Total rows in player_stats_defense grouped by season
SELECT season,
       COUNT(*) AS row_count
FROM player_stats_defense
GROUP BY season
ORDER BY season;

-- Returning production percentages for LSU in 2025
SELECT rs.season,
       rs.team_id,
       t.school,
       rs.off_pct,
       rs.def_pct,
       rs.overall_pct
FROM returning_summary AS rs
JOIN teams AS t
  ON t.team_id = rs.team_id
WHERE t.school = 'LSU'
  AND rs.season = 2025;
