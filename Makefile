.PHONY: up down reset-db teams rosters stats ret inc api

COMPOSE := docker compose -f infra/docker-compose.yml
PYTHON ?= python
ALEMBIC ?= alembic
UVICORN ?= uvicorn

TEAMS_YEAR ?= 2024
ROSTER_YEARS ?= 2024
STATS_YEARS ?= 2024
RET_SEASONS ?=
INC_SEASONS ?=
ROSTER_TEAM ?=
STATS_TEAM ?=
RET_TEAM ?=
INC_TEAM ?=
API_HOST ?= 0.0.0.0
API_PORT ?= 8000

up:
	$(COMPOSE) up -d

down:
	$(COMPOSE) down

reset-db:
	$(ALEMBIC) downgrade base
	$(ALEMBIC) upgrade head

teams:
	$(PYTHON) -c "from etl.load_teams import main; main($(TEAMS_YEAR))"

rosters:
	$(PYTHON) -m etl.load_rosters $(if $(strip $(ROSTER_TEAM)),--team "$(ROSTER_TEAM)",--all) $(foreach year,$(ROSTER_YEARS),--year $(year))

stats:
	$(PYTHON) -m etl.load_player_stats $(foreach year,$(STATS_YEARS),--year $(year)) $(if $(strip $(STATS_TEAM)),--team "$(STATS_TEAM)",--all)

ret:
	$(PYTHON) -m etl.compute_returning $(if $(strip $(RET_TEAM)),--team "$(RET_TEAM)") $(foreach season,$(RET_SEASONS),--season $(season))

inc:
	$(PYTHON) -m etl.compute_incoming $(if $(strip $(INC_TEAM)),--team "$(INC_TEAM)") $(foreach season,$(INC_SEASONS),--season $(season))

api:
	$(UVICORN) api.main:app --host $(API_HOST) --port $(API_PORT) --reload
