"""add coach changes table

Revision ID: c5f8b29a4e61
Revises: a3c9e17b5d42
Create Date: 2026-08-10 18:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c5f8b29a4e61'
down_revision: Union[str, Sequence[str], None] = 'a3c9e17b5d42'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table('coach_changes',
    sa.Column('season', sa.Integer(), nullable=False),
    sa.Column('team_id', sa.Integer(), nullable=False),
    sa.Column('new_head_coach', sa.Boolean(), nullable=False),
    sa.Column('is_interim', sa.Boolean(), nullable=False),
    sa.Column('coach_name', sa.String(), nullable=True),
    sa.Column('tenure_start_year', sa.Integer(), nullable=True),
    sa.ForeignKeyConstraint(['team_id'], ['teams.team_id'], ),
    sa.PrimaryKeyConstraint('season', 'team_id')
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table('coach_changes')
