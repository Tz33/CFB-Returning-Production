"""add incoming summary table

Revision ID: 4b334dfe2675
Revises: 3db0b43d2fb4
Create Date: 2025-09-10 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "4b334dfe2675"
down_revision: Union[str, Sequence[str], None] = "3db0b43d2fb4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create incoming summary table."""

    op.create_table(
        "incoming_summary",
        sa.Column("season", sa.Integer(), nullable=False),
        sa.Column("team_id", sa.Integer(), nullable=False),
        sa.Column("transfer_share", sa.Float(), nullable=False),
        sa.Column("freshman_count", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["team_id"], ["teams.team_id"]),
        sa.PrimaryKeyConstraint("season", "team_id"),
    )


def downgrade() -> None:
    """Drop incoming summary table."""

    op.drop_table("incoming_summary")
