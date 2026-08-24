from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy import String, Integer, BigInteger, Float, Boolean, ForeignKey

class Base(DeclarativeBase): pass

class Team(Base):
    __tablename__ = "teams"
    team_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    school: Mapped[str] = mapped_column(String, unique=True)
    conference: Mapped[str | None] = mapped_column(String, nullable=True)

class Player(Base):
    __tablename__ = "players"
    player_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    full_name: Mapped[str] = mapped_column(String)
    primary_pos: Mapped[str | None] = mapped_column(String, nullable=True)


class Roster(Base):
    __tablename__ = "rosters"
    season: Mapped[int] = mapped_column(primary_key=True)
    team_id: Mapped[int] = mapped_column(ForeignKey("teams.team_id"), primary_key=True)
    player_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    full_name: Mapped[str] = mapped_column(String)
    position: Mapped[str | None] = mapped_column(String, nullable=True)
    jersey: Mapped[int | None] = mapped_column(nullable=True)
    player_cfbd_id: Mapped[int | None] = mapped_column(index=True, nullable=True)

class PlayerStatsOffense(Base):
    __tablename__ = "player_stats_offense"
    season: Mapped[int] = mapped_column(Integer, primary_key=True)
    team_id: Mapped[int] = mapped_column(ForeignKey("teams.team_id"), primary_key=True)
    player_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)

    passing_yards: Mapped[int] = mapped_column(Integer)
    rushing_yards: Mapped[int] = mapped_column(Integer)
    receiving_yards: Mapped[int] = mapped_column(Integer)
    total_yards: Mapped[int] = mapped_column(Integer)
    touchdowns: Mapped[int] = mapped_column(Integer)
    receptions: Mapped[int] = mapped_column(Integer)

class PlayerStatsDefense(Base):
    __tablename__ = "player_stats_defense"
    season: Mapped[int] = mapped_column(Integer, primary_key=True)
    team_id: Mapped[int] = mapped_column(ForeignKey("teams.team_id"), primary_key=True)
    player_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)

    tackles: Mapped[int] = mapped_column(Integer)
    tackles_for_loss: Mapped[float] = mapped_column(Float)
    sacks: Mapped[float] = mapped_column(Float)
    interceptions: Mapped[int] = mapped_column(Integer)
    touchdowns: Mapped[int] = mapped_column(Integer)

class ReturningSummary(Base):
    __tablename__ = "returning_summary"
    season: Mapped[int] = mapped_column(Integer, primary_key=True)
    team_id: Mapped[int] = mapped_column(ForeignKey("teams.team_id"), primary_key=True)

    off_pct: Mapped[float] = mapped_column(Float)
    def_pct: Mapped[float] = mapped_column(Float)
    overall_pct: Mapped[float] = mapped_column(Float)

class IncomingSummary(Base):
    __tablename__ = "incoming_summary"
    season: Mapped[int] = mapped_column(Integer, primary_key=True)
    team_id: Mapped[int] = mapped_column(ForeignKey("teams.team_id"), primary_key=True)

    transfer_share: Mapped[float] = mapped_column(Float)
    freshman_count: Mapped[int] = mapped_column(Integer)

class ReturningDetail(Base):
    __tablename__ = "returning_detail"
    season: Mapped[int] = mapped_column(Integer, primary_key=True)
    team_id: Mapped[int] = mapped_column(ForeignKey("teams.team_id"), primary_key=True)

    # per-category shares of prior-season production from returning players;
    # NULL (not 0.0) when the prior-season denominator is zero
    ret_passing_yards: Mapped[float | None] = mapped_column(Float, nullable=True)
    ret_rushing_yards: Mapped[float | None] = mapped_column(Float, nullable=True)
    ret_receiving_yards: Mapped[float | None] = mapped_column(Float, nullable=True)
    ret_receptions: Mapped[float | None] = mapped_column(Float, nullable=True)
    ret_tackles: Mapped[float | None] = mapped_column(Float, nullable=True)
    ret_sacks: Mapped[float | None] = mapped_column(Float, nullable=True)
    ret_tackles_for_loss: Mapped[float | None] = mapped_column(Float, nullable=True)
    ret_interceptions: Mapped[float | None] = mapped_column(Float, nullable=True)

    weighted_off_pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    weighted_def_pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    weighted_overall_pct: Mapped[float | None] = mapped_column(Float, nullable=True)

    # continuity index including translated incoming-transfer production (2021+);
    # an index, not a share — can exceed 1.0
    adjusted_off_pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    adjusted_def_pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    adjusted_overall_pct: Mapped[float | None] = mapped_column(Float, nullable=True)

    # share of prior-season OL games-started returning (NCAA GP/GS source);
    # NULL when no prior-season OL starts are recorded
    ret_ol_starts_share: Mapped[float | None] = mapped_column(Float, nullable=True)

class WinProjection(Base):
    __tablename__ = "win_projections"
    season: Mapped[int] = mapped_column(Integer, primary_key=True)
    team_id: Mapped[int] = mapped_column(ForeignKey("teams.team_id"), primary_key=True)

    rating_pred: Mapped[float] = mapped_column(Float)
    n_games: Mapped[int] = mapped_column(Integer)
    expected_wins: Mapped[float] = mapped_column(Float)
    p_ge_6: Mapped[float] = mapped_column(Float)
    p_ge_8: Mapped[float] = mapped_column(Float)
    p_ge_10: Mapped[float] = mapped_column(Float)
    win_dist: Mapped[str] = mapped_column(String)  # JSON array, P(0 wins)..P(n_games wins)
    model_version: Mapped[str | None] = mapped_column(String, nullable=True)

class Recruiting(Base):
    __tablename__ = "recruiting"
    season: Mapped[int] = mapped_column(Integer, primary_key=True)
    team_id: Mapped[int] = mapped_column(ForeignKey("teams.team_id"), primary_key=True)

    rank: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # raw source points; scale drifts across eras — z-scored within season at fit time
    points: Mapped[float | None] = mapped_column(Float, nullable=True)

class Game(Base):
    __tablename__ = "games"
    game_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    season: Mapped[int] = mapped_column(Integer, index=True)
    week: Mapped[int | None] = mapped_column(Integer, nullable=True)
    season_type: Mapped[str | None] = mapped_column(String, nullable=True)

    # NULL team_id = non-FBS side; raw school names kept for FCS opponents in reports
    home_team_id: Mapped[int | None] = mapped_column(ForeignKey("teams.team_id"), nullable=True)
    away_team_id: Mapped[int | None] = mapped_column(ForeignKey("teams.team_id"), nullable=True)
    home_school: Mapped[str | None] = mapped_column(String, nullable=True)
    away_school: Mapped[str | None] = mapped_column(String, nullable=True)
    home_classification: Mapped[str | None] = mapped_column(String, nullable=True)
    away_classification: Mapped[str | None] = mapped_column(String, nullable=True)
    neutral_site: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    conference_game: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    home_points: Mapped[int | None] = mapped_column(Integer, nullable=True)
    away_points: Mapped[int | None] = mapped_column(Integer, nullable=True)
    completed: Mapped[bool] = mapped_column(Boolean, default=False)

class WinTotal(Base):
    __tablename__ = "win_totals"
    season: Mapped[int] = mapped_column(Integer, primary_key=True)
    team_id: Mapped[int] = mapped_column(ForeignKey("teams.team_id"), primary_key=True)

    win_total: Mapped[float] = mapped_column(Float)
    over_odds: Mapped[int | None] = mapped_column(Integer, nullable=True)
    under_odds: Mapped[int | None] = mapped_column(Integer, nullable=True)
    source: Mapped[str | None] = mapped_column(String, nullable=True)

class PlayerParticipation(Base):
    """Per-player games played/started, scraped from stats.ncaa.org rosters.

    Covers positions that accrue no box-score stats (OL especially). Players
    are keyed by name within a team-season because NCAA has no id shared with
    CFBD; cross-source joins go through db.names.normalize_player_name.
    """
    __tablename__ = "player_participation"
    season: Mapped[int] = mapped_column(Integer, primary_key=True)
    team_id: Mapped[int] = mapped_column(ForeignKey("teams.team_id"), primary_key=True)
    player_name: Mapped[str] = mapped_column(String, primary_key=True)

    class_year: Mapped[str | None] = mapped_column(String, nullable=True)
    position: Mapped[str | None] = mapped_column(String, nullable=True)
    games_played: Mapped[int] = mapped_column(Integer)
    games_started: Mapped[int] = mapped_column(Integer)
    source: Mapped[str | None] = mapped_column(String, nullable=True)

class GameLine(Base):
    __tablename__ = "game_lines"
    game_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    season: Mapped[int] = mapped_column(Integer, index=True)
    week: Mapped[int | None] = mapped_column(Integer, nullable=True)
    season_type: Mapped[str | None] = mapped_column(String, nullable=True)

    # NULL team_id = non-FBS side, filtered at analysis time
    home_team_id: Mapped[int | None] = mapped_column(ForeignKey("teams.team_id"), nullable=True)
    away_team_id: Mapped[int | None] = mapped_column(ForeignKey("teams.team_id"), nullable=True)
    home_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    away_score: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # home-relative: negative = home favored
    spread: Mapped[float | None] = mapped_column(Float, nullable=True)
    spread_open: Mapped[float | None] = mapped_column(Float, nullable=True)
    over_under: Mapped[float | None] = mapped_column(Float, nullable=True)
    provider: Mapped[str | None] = mapped_column(String, nullable=True)

class TeamSeason(Base):
    __tablename__ = "team_seasons"
    season: Mapped[int] = mapped_column(Integer, primary_key=True)
    team_id: Mapped[int] = mapped_column(ForeignKey("teams.team_id"), primary_key=True)

    conference: Mapped[str | None] = mapped_column(String, nullable=True)
    classification: Mapped[str] = mapped_column(String, default="fbs")

class CoachChange(Base):
    __tablename__ = "coach_changes"
    season: Mapped[int] = mapped_column(Integer, primary_key=True)
    team_id: Mapped[int] = mapped_column(ForeignKey("teams.team_id"), primary_key=True)

    new_head_coach: Mapped[bool] = mapped_column(Boolean)
    is_interim: Mapped[bool] = mapped_column(Boolean, default=False)
    coach_name: Mapped[str | None] = mapped_column(String, nullable=True)
    tenure_start_year: Mapped[int | None] = mapped_column(Integer, nullable=True)

class TeamOutcome(Base):
    __tablename__ = "team_outcomes"
    season: Mapped[int] = mapped_column(Integer, primary_key=True)
    team_id: Mapped[int] = mapped_column(ForeignKey("teams.team_id"), primary_key=True)

    # nullable: a team can have a record but no SP+ row (or vice versa) in old seasons
    wins: Mapped[int | None] = mapped_column(Integer, nullable=True)
    losses: Mapped[int | None] = mapped_column(Integer, nullable=True)
    win_pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    sp_rating: Mapped[float | None] = mapped_column(Float, nullable=True)
