"""add win totals table

Revision ID: b9e4d20c7f18
Revises: f2a6c88d1b73
Create Date: 2026-08-10 21:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b9e4d20c7f18'
down_revision: Union[str, Sequence[str], None] = 'f2a6c88d1b73'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table('win_totals',
    sa.Column('season', sa.Integer(), nullable=False),
    sa.Column('team_id', sa.Integer(), nullable=False),
    sa.Column('win_total', sa.Float(), nullable=False),
    sa.Column('over_odds', sa.Integer(), nullable=True),
    sa.Column('under_odds', sa.Integer(), nullable=True),
    sa.Column('source', sa.String(), nullable=True),
    sa.ForeignKeyConstraint(['team_id'], ['teams.team_id'], ),
    sa.PrimaryKeyConstraint('season', 'team_id')
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table('win_totals')
