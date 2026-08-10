from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy import String, Integer, BigInteger, Float, ForeignKey

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
