"""add returning summary table

Revision ID: 3db0b43d2fb4
Revises: 2e7b2df52a19
Create Date: 2025-09-09 22:20:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "3db0b43d2fb4"
down_revision: Union[str, Sequence[str], None] = "2e7b2df52a19"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create returning summary table."""

    op.create_table(
        "returning_summary",
        sa.Column("season", sa.Integer(), nullable=False),
        sa.Column("team_id", sa.Integer(), nullable=False),
        sa.Column("off_pct", sa.Float(), nullable=False),
        sa.Column("def_pct", sa.Float(), nullable=False),
        sa.Column("overall_pct", sa.Float(), nullable=False),
        sa.ForeignKeyConstraint(["team_id"], ["teams.team_id"]),
        sa.PrimaryKeyConstraint("season", "team_id"),
    )


def downgrade() -> None:
    """Drop returning summary table."""

    op.drop_table("returning_summary")
