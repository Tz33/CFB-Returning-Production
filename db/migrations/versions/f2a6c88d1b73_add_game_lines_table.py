"""add game lines table

Revision ID: f2a6c88d1b73
Revises: e8d1f47c3a95
Create Date: 2026-08-10 20:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f2a6c88d1b73'
down_revision: Union[str, Sequence[str], None] = 'e8d1f47c3a95'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table('game_lines',
    sa.Column('game_id', sa.BigInteger(), nullable=False),
    sa.Column('season', sa.Integer(), nullable=False),
    sa.Column('week', sa.Integer(), nullable=True),
    sa.Column('season_type', sa.String(), nullable=True),
    sa.Column('home_team_id', sa.Integer(), nullable=True),
    sa.Column('away_team_id', sa.Integer(), nullable=True),
    sa.Column('home_score', sa.Integer(), nullable=True),
    sa.Column('away_score', sa.Integer(), nullable=True),
    sa.Column('spread', sa.Float(), nullable=True),
    sa.Column('spread_open', sa.Float(), nullable=True),
    sa.Column('over_under', sa.Float(), nullable=True),
    sa.Column('provider', sa.String(), nullable=True),
    sa.ForeignKeyConstraint(['home_team_id'], ['teams.team_id'], ),
    sa.ForeignKeyConstraint(['away_team_id'], ['teams.team_id'], ),
    sa.PrimaryKeyConstraint('game_id')
    )
    op.create_index(op.f('ix_game_lines_season'), 'game_lines', ['season'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f('ix_game_lines_season'), table_name='game_lines')
    op.drop_table('game_lines')
