"""Tests for per-category returning shares and the weighted composite."""
from __future__ import annotations

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from db import metrics
from db.models import Base, PlayerStatsOffense, Roster, Team
from db.weights import weighted_composite
from etl import compute_returning_detail


@pytest.fixture()
def session_factory():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)


def _seed(session):
    session.add(Team(team_id=1, school="Toy U"))
    # 2023 producers: player 10 (returns in 2024), player 11 (leaves)
    session.add_all([
        Roster(season=2023, team_id=1, player_id=10, full_name="Returner"),
        Roster(season=2023, team_id=1, player_id=11, full_name="Leaver"),
        Roster(season=2024, team_id=1, player_id=10, full_name="Returner"),
    ])
    session.add_all([
        PlayerStatsOffense(season=2023, team_id=1, player_id=10,
                           passing_yards=0, rushing_yards=100, receiving_yards=300,
                           total_yards=400, touchdowns=4, receptions=30),
        PlayerStatsOffense(season=2023, team_id=1, player_id=11,
                           passing_yards=2000, rushing_yards=100, receiving_yards=100,
                           total_yards=2200, touchdowns=20, receptions=10),
    ])
    session.commit()


def test_category_shares_differ(session_factory, monkeypatch):
    monkeypatch.setattr(metrics, "SessionLocal", session_factory)
    with session_factory() as s:
        _seed(s)
        # receiving: returner has 300 of 400; receptions: 30 of 40; passing: 0 of 2000
        recv = compute_returning_detail._category_share(
            s, team_id=1, season=2024,
            table=PlayerStatsOffense, value_column=PlayerStatsOffense.receiving_yards)
        rec = compute_returning_detail._category_share(
            s, team_id=1, season=2024,
            table=PlayerStatsOffense, value_column=PlayerStatsOffense.receptions)
        passing = compute_returning_detail._category_share(
            s, team_id=1, season=2024,
            table=PlayerStatsOffense, value_column=PlayerStatsOffense.passing_yards)
        assert recv == pytest.approx(300 / 400)
        assert rec == pytest.approx(30 / 40)
        assert passing == pytest.approx(0.0)


def test_zero_denominator_is_none(session_factory, monkeypatch):
    monkeypatch.setattr(metrics, "SessionLocal", session_factory)
    with session_factory() as s:
        _seed(s)
        # no defense stats seeded -> tackles denominator is zero -> None, not 0.0
        from db.models import PlayerStatsDefense
        share = compute_returning_detail._category_share(
            s, team_id=1, season=2024,
            table=PlayerStatsDefense, value_column=PlayerStatsDefense.tackles)
        assert share is None


def test_weighted_composite_math():
    weights = {"a": 0.5, "b": 0.3, "c": 0.2}
    assert weighted_composite({"a": 1.0, "b": 0.0, "c": 0.5}, weights) == pytest.approx(0.6)


def test_weighted_composite_renormalizes_over_nulls():
    weights = {"a": 0.5, "b": 0.3, "c": 0.2}
    # c is null -> weights renormalize over a and b: (1.0*0.5 + 0.0*0.3) / 0.8
    assert weighted_composite({"a": 1.0, "b": 0.0, "c": None}, weights) == pytest.approx(0.625)


def test_weighted_composite_all_null_or_empty():
    weights = {"a": 1.0}
    assert weighted_composite({"a": None}, weights) is None
    assert weighted_composite({"a": 0.5}, {}) is None
