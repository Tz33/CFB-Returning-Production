# CFB Returning Production

Utilities for loading CollegeFootballData rosters and stats into Postgres and computing returning and incoming production summaries.

## Setup

1. Install dependencies with `pip install -r requirements.txt`.
2. Set `CFBD_API_KEY` in your environment or a `.env` file before running ETL scripts.
3. Configure the database connection via `DATABASE_URL` (defaults to local Postgres in `alembic.ini`).

## Make Targets

The included `Makefile` wraps the most common project workflows:

- `make up` / `make down` – start or stop the Docker Compose stack in `infra/docker-compose.yml`.
- `make reset-db` – drop and reapply all Alembic migrations.
- `make teams TEAMS_YEAR=2024` – seed the `teams` table for the requested season.
- `make rosters ROSTER_YEARS="2024 2025" [ROSTER_TEAM="LSU"]` – load rosters for the listed seasons (optionally for a single team).
- `make stats STATS_YEARS="2024 2025" [STATS_TEAM="LSU"]` – load player offense and defense stats.
- `make ret RET_SEASONS="2025" [RET_TEAM="LSU"]` – compute returning production percentages.
- `make inc INC_SEASONS="2025" [INC_TEAM="LSU"]` – compute incoming player mix metrics.
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
