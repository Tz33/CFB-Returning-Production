"""add player stats tables

Revision ID: 1f24c56c9270
Revises: 05c2f374f91b
Create Date: 2025-09-09 22:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '1f24c56c9270'
down_revision: Union[str, Sequence[str], None] = '05c2f374f91b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        'player_stats_offense',
        sa.Column('season', sa.Integer(), nullable=False),
        sa.Column('team_id', sa.Integer(), nullable=False),
        sa.Column('player_id', sa.BigInteger(), nullable=False),
        sa.Column('passing_yards', sa.Integer(), nullable=False),
        sa.Column('rushing_yards', sa.Integer(), nullable=False),
        sa.Column('receiving_yards', sa.Integer(), nullable=False),
        sa.Column('total_yards', sa.Integer(), nullable=False),
        sa.Column('touchdowns', sa.Integer(), nullable=False),
        sa.Column('receptions', sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(['team_id'], ['teams.team_id']),
        sa.PrimaryKeyConstraint('season', 'team_id', 'player_id'),
    )
    op.create_table(
        'player_stats_defense',
        sa.Column('season', sa.Integer(), nullable=False),
        sa.Column('team_id', sa.Integer(), nullable=False),
        sa.Column('player_id', sa.BigInteger(), nullable=False),
        sa.Column('tackles', sa.Integer(), nullable=False),
        sa.Column('tackles_for_loss', sa.Integer(), nullable=False),
        sa.Column('sacks', sa.Integer(), nullable=False),
        sa.Column('interceptions', sa.Integer(), nullable=False),
        sa.Column('touchdowns', sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(['team_id'], ['teams.team_id']),
        sa.PrimaryKeyConstraint('season', 'team_id', 'player_id'),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table('player_stats_defense')
    op.drop_table('player_stats_offense')
