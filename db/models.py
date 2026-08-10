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

class WinTotal(Base):
    __tablename__ = "win_totals"
    season: Mapped[int] = mapped_column(Integer, primary_key=True)
    team_id: Mapped[int] = mapped_column(ForeignKey("teams.team_id"), primary_key=True)

    win_total: Mapped[float] = mapped_column(Float)
    over_odds: Mapped[int | None] = mapped_column(Integer, nullable=True)
    under_odds: Mapped[int | None] = mapped_column(Integer, nullable=True)
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
