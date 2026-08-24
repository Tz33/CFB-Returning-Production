"""add player participation table and ol starts share column

Revision ID: b6c2e84d1f59
Revises: a7f3d81c4e29
Create Date: 2026-08-24 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b6c2e84d1f59'
down_revision: Union[str, Sequence[str], None] = 'a7f3d81c4e29'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table('player_participation',
    sa.Column('season', sa.Integer(), nullable=False),
    sa.Column('team_id', sa.Integer(), nullable=False),
    sa.Column('player_name', sa.String(), nullable=False),
    sa.Column('class_year', sa.String(), nullable=True),
    sa.Column('position', sa.String(), nullable=True),
    sa.Column('games_played', sa.Integer(), nullable=False),
    sa.Column('games_started', sa.Integer(), nullable=False),
    sa.Column('source', sa.String(), nullable=True),
    sa.ForeignKeyConstraint(['team_id'], ['teams.team_id'], ),
    sa.PrimaryKeyConstraint('season', 'team_id', 'player_name')
    )
    op.add_column('returning_detail',
                  sa.Column('ret_ol_starts_share', sa.Float(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('returning_detail', 'ret_ol_starts_share')
    op.drop_table('player_participation')
