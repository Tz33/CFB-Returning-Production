"""Unit tests for metrics helper functions using toy datasets."""

from __future__ import annotations

import os
import pathlib
import sys

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

# Ensure the application's session module binds to an in-memory database during tests.
os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")

from db import metrics  # noqa: E402 (requires DATABASE_URL)
from db.models import Base, PlayerStatsOffense, Roster, Team  # noqa: E402


@pytest.fixture()
def engine():
    """Provide a SQLite engine that mimics the project's metadata in memory."""

    engine = create_engine(
        "sqlite://",
        future=True,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    with engine.begin() as connection:
        # Metrics expect mv_incoming to exist. A simple table is sufficient for tests.
        connection.exec_driver_sql(
            "CREATE TABLE mv_incoming (season INTEGER, team_id INTEGER, player_id INTEGER)"
        )
    try:
        yield engine
    finally:
        engine.dispose()


@pytest.fixture()
def session(engine) -> Session:
    """Yield a SQLAlchemy session bound to the in-memory engine."""

    SessionLocal = sessionmaker(bind=engine, future=True, autoflush=False)
    with SessionLocal() as session:
        yield session
        session.rollback()


@pytest.fixture()
def session_factory(engine):
    """Session factory hooked to the in-memory engine for monkeypatching metrics."""

    return sessionmaker(bind=engine, future=True, autoflush=False)


@pytest.fixture()
def returning_scenario(session):
    """Seed a toy dataset with one returning contributor and one departure."""

    session.add_all(
        [
            Team(team_id=1, school="Toy Tech", conference=None),
        ]
    )
    session.add_all(
        [
            Roster(
                season=2021,
                team_id=1,
                player_id=10,
                full_name="Returning QB",
                position="QB",
                jersey=None,
                player_cfbd_id=None,
            ),
            Roster(
                season=2021,
                team_id=1,
                player_id=20,
                full_name="Departed RB",
                position="RB",
                jersey=None,
                player_cfbd_id=None,
            ),
            Roster(
                season=2022,
                team_id=1,
                player_id=10,
                full_name="Returning QB",
                position="QB",
                jersey=None,
                player_cfbd_id=None,
            ),
            Roster(
                season=2022,
                team_id=1,
                player_id=30,
                full_name="New WR",
                position="WR",
                jersey=None,
                player_cfbd_id=None,
            ),
        ]
    )
    session.add_all(
        [
            PlayerStatsOffense(
                season=2021,
                team_id=1,
                player_id=10,
                passing_yards=120,
                rushing_yards=80,
                receiving_yards=0,
                total_yards=200,
                touchdowns=2,
                receptions=0,
            ),
            PlayerStatsOffense(
                season=2021,
                team_id=1,
                player_id=20,
                passing_yards=0,
                rushing_yards=500,
                receiving_yards=0,
                total_yards=500,
                touchdowns=5,
                receptions=0,
            ),
        ]
    )
    session.commit()

    yield {"team_id": 1, "season": 2022, "expected_share": 200 / 700}

    session.execute(text("DELETE FROM player_stats_offense"))
    session.execute(text("DELETE FROM rosters"))
    session.execute(text("DELETE FROM teams"))
    session.commit()


@pytest.fixture()
def incoming_scenario(session):
    """Seed incoming players including one transfer and one true freshman."""

    session.add_all(
        [
            Team(team_id=1, school="Toy Tech", conference=None),
            Team(team_id=2, school="Transfer U", conference=None),
        ]
    )
    session.add_all(
        [
            Roster(
                season=2021,
                team_id=2,
                player_id=40,
                full_name="Transfer QB",
                position="QB",
                jersey=None,
                player_cfbd_id=None,
            ),
            Roster(
                season=2022,
                team_id=1,
                player_id=40,
                full_name="Transfer QB",
                position="QB",
                jersey=None,
                player_cfbd_id=None,
            ),
            Roster(
                season=2022,
                team_id=1,
                player_id=50,
                full_name="Freshman RB",
                position="RB",
                jersey=None,
                player_cfbd_id=None,
            ),
        ]
    )
    session.execute(
        text(
            "INSERT INTO mv_incoming (season, team_id, player_id) VALUES (:season, :team, :player)"
        ),
        {"season": 2022, "team": 1, "player": 40},
    )
    session.execute(
        text(
            "INSERT INTO mv_incoming (season, team_id, player_id) VALUES (:season, :team, :player)"
        ),
        {"season": 2022, "team": 1, "player": 50},
    )
    session.commit()

    yield {"team_id": 1, "season": 2022, "expected": {"transfers": 1, "freshmen": 1}}

    session.execute(text("DELETE FROM mv_incoming"))
    session.execute(text("DELETE FROM rosters"))
    session.execute(text("DELETE FROM teams"))
    session.commit()


def test_calculate_returning_percentage(monkeypatch: pytest.MonkeyPatch, session_factory, returning_scenario):
    """Returning share equals the ratio of returning yards to total yards from last year."""

    monkeypatch.setattr(metrics, "SessionLocal", session_factory)

    result = metrics.calculate_returning_percentage(
        returning_scenario["team_id"],
        returning_scenario["season"],
    )

    assert result == pytest.approx(returning_scenario["expected_share"])


def test_classify_incoming_counts_transfers_and_freshmen(session, incoming_scenario):
    """Incoming players are split based on whether they appeared on another roster last year."""

    result = metrics.classify_incoming(
        incoming_scenario["team_id"],
        incoming_scenario["season"],
        session=session,
    )

    assert result == incoming_scenario["expected"]

