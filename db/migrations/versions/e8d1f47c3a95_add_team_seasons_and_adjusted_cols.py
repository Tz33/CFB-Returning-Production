"""add team seasons table and adjusted returning columns

Revision ID: e8d1f47c3a95
Revises: c5f8b29a4e61
Create Date: 2026-08-10 19:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e8d1f47c3a95'
down_revision: Union[str, Sequence[str], None] = 'c5f8b29a4e61'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table('team_seasons',
    sa.Column('season', sa.Integer(), nullable=False),
    sa.Column('team_id', sa.Integer(), nullable=False),
    sa.Column('conference', sa.String(), nullable=True),
    sa.Column('classification', sa.String(), nullable=False),
    sa.ForeignKeyConstraint(['team_id'], ['teams.team_id'], ),
    sa.PrimaryKeyConstraint('season', 'team_id')
    )
    op.add_column('returning_detail', sa.Column('adjusted_off_pct', sa.Float(), nullable=True))
    op.add_column('returning_detail', sa.Column('adjusted_def_pct', sa.Float(), nullable=True))
    op.add_column('returning_detail', sa.Column('adjusted_overall_pct', sa.Float(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('returning_detail', 'adjusted_overall_pct')
    op.drop_column('returning_detail', 'adjusted_def_pct')
    op.drop_column('returning_detail', 'adjusted_off_pct')
    op.drop_table('team_seasons')
