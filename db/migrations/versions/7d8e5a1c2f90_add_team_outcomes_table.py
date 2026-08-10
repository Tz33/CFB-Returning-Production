"""add team outcomes table

Revision ID: 7d8e5a1c2f90
Revises: 4b334dfe2675
Create Date: 2026-08-10 15:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '7d8e5a1c2f90'
down_revision: Union[str, Sequence[str], None] = '4b334dfe2675'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table('team_outcomes',
    sa.Column('season', sa.Integer(), nullable=False),
    sa.Column('team_id', sa.Integer(), nullable=False),
    sa.Column('wins', sa.Integer(), nullable=True),
    sa.Column('losses', sa.Integer(), nullable=True),
    sa.Column('win_pct', sa.Float(), nullable=True),
    sa.Column('sp_rating', sa.Float(), nullable=True),
    sa.ForeignKeyConstraint(['team_id'], ['teams.team_id'], ),
    sa.PrimaryKeyConstraint('season', 'team_id')
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table('team_outcomes')
