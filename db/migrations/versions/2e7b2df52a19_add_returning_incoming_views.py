"""add returning and incoming materialized views

Revision ID: 2e7b2df52a19
Revises: 1f24c56c9270
Create Date: 2025-09-09 22:10:00.000000
"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "2e7b2df52a19"
down_revision: Union[str, Sequence[str], None] = "1f24c56c9270"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create materialized views for returning and incoming players."""
    op.execute(
        """
        CREATE MATERIALIZED VIEW mv_returning AS
        SELECT
            curr.season,
            curr.team_id,
            curr.player_id,
            curr.full_name,
            curr.position,
            curr.jersey,
            curr.player_cfbd_id
        FROM rosters AS curr
        INNER JOIN rosters AS prev
            ON prev.season = curr.season - 1
           AND prev.team_id = curr.team_id
           AND prev.player_id = curr.player_id;
        """
    )

    op.execute(
        """
        CREATE MATERIALIZED VIEW mv_incoming AS
        SELECT
            curr.season,
            curr.team_id,
            curr.player_id,
            curr.full_name,
            curr.position,
            curr.jersey,
            curr.player_cfbd_id
        FROM rosters AS curr
        LEFT JOIN rosters AS prev
            ON prev.season = curr.season - 1
           AND prev.team_id = curr.team_id
           AND prev.player_id = curr.player_id
        WHERE prev.player_id IS NULL;
        """
    )


def downgrade() -> None:
    """Drop materialized views for returning and incoming players."""
    op.execute("DROP MATERIALIZED VIEW IF EXISTS mv_incoming;")
    op.execute("DROP MATERIALIZED VIEW IF EXISTS mv_returning;")
