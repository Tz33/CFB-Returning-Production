"""add games table

Revision ID: d4b7f92e6a53
Revises: b9e4d20c7f18
Create Date: 2026-08-10 23:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd4b7f92e6a53'
down_revision: Union[str, Sequence[str], None] = 'b9e4d20c7f18'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table('games',
    sa.Column('game_id', sa.BigInteger(), nullable=False),
    sa.Column('season', sa.Integer(), nullable=False),
    sa.Column('week', sa.Integer(), nullable=True),
    sa.Column('season_type', sa.String(), nullable=True),
    sa.Column('home_team_id', sa.Integer(), nullable=True),
    sa.Column('away_team_id', sa.Integer(), nullable=True),
    sa.Column('home_school', sa.String(), nullable=True),
    sa.Column('away_school', sa.String(), nullable=True),
    sa.Column('home_classification', sa.String(), nullable=True),
    sa.Column('away_classification', sa.String(), nullable=True),
    sa.Column('neutral_site', sa.Boolean(), nullable=True),
    sa.Column('conference_game', sa.Boolean(), nullable=True),
    sa.Column('home_points', sa.Integer(), nullable=True),
    sa.Column('away_points', sa.Integer(), nullable=True),
    sa.Column('completed', sa.Boolean(), nullable=False, server_default=sa.false()),
    sa.ForeignKeyConstraint(['home_team_id'], ['teams.team_id'], ),
    sa.ForeignKeyConstraint(['away_team_id'], ['teams.team_id'], ),
    sa.PrimaryKeyConstraint('game_id')
    )
    op.create_index(op.f('ix_games_season'), 'games', ['season'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f('ix_games_season'), table_name='games')
    op.drop_table('games')
