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
