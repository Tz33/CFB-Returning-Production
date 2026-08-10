"""add returning detail table

Revision ID: a3c9e17b5d42
Revises: 7d8e5a1c2f90
Create Date: 2026-08-10 17:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a3c9e17b5d42'
down_revision: Union[str, Sequence[str], None] = '7d8e5a1c2f90'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table('returning_detail',
    sa.Column('season', sa.Integer(), nullable=False),
    sa.Column('team_id', sa.Integer(), nullable=False),
    sa.Column('ret_passing_yards', sa.Float(), nullable=True),
    sa.Column('ret_rushing_yards', sa.Float(), nullable=True),
    sa.Column('ret_receiving_yards', sa.Float(), nullable=True),
    sa.Column('ret_receptions', sa.Float(), nullable=True),
    sa.Column('ret_tackles', sa.Float(), nullable=True),
    sa.Column('ret_sacks', sa.Float(), nullable=True),
    sa.Column('ret_tackles_for_loss', sa.Float(), nullable=True),
    sa.Column('ret_interceptions', sa.Float(), nullable=True),
    sa.Column('weighted_off_pct', sa.Float(), nullable=True),
    sa.Column('weighted_def_pct', sa.Float(), nullable=True),
    sa.Column('weighted_overall_pct', sa.Float(), nullable=True),
    sa.ForeignKeyConstraint(['team_id'], ['teams.team_id'], ),
    sa.PrimaryKeyConstraint('season', 'team_id')
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table('returning_detail')
