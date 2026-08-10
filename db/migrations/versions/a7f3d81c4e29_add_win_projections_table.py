"""add win projections table

Revision ID: a7f3d81c4e29
Revises: c1e8a35d9b27
Create Date: 2026-08-11 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a7f3d81c4e29'
down_revision: Union[str, Sequence[str], None] = 'c1e8a35d9b27'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table('win_projections',
    sa.Column('season', sa.Integer(), nullable=False),
    sa.Column('team_id', sa.Integer(), nullable=False),
    sa.Column('rating_pred', sa.Float(), nullable=False),
    sa.Column('n_games', sa.Integer(), nullable=False),
    sa.Column('expected_wins', sa.Float(), nullable=False),
    sa.Column('p_ge_6', sa.Float(), nullable=False),
    sa.Column('p_ge_8', sa.Float(), nullable=False),
    sa.Column('p_ge_10', sa.Float(), nullable=False),
    sa.Column('win_dist', sa.String(), nullable=False),
    sa.Column('model_version', sa.String(), nullable=True),
    sa.ForeignKeyConstraint(['team_id'], ['teams.team_id'], ),
    sa.PrimaryKeyConstraint('season', 'team_id')
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table('win_projections')
