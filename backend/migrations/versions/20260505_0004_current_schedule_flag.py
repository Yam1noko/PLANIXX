"""add current schedule flag

Revision ID: 20260505_0004
Revises: 20260504_0003
Create Date: 2026-05-05 18:10:00
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260505_0004"
down_revision = "20260504_0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "schedules",
        sa.Column(
            "is_current",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
    )
    op.create_index("ix_schedules_is_current", "schedules", ["is_current"], unique=False)

    op.execute(
        """
        WITH ranked AS (
            SELECT
                id,
                ROW_NUMBER() OVER (
                    PARTITION BY user_id
                    ORDER BY created_at DESC, id DESC
                ) AS row_num
            FROM schedules
        )
        UPDATE schedules
        SET is_current = (ranked.row_num = 1)
        FROM ranked
        WHERE schedules.id = ranked.id
        """
    )

    op.alter_column("schedules", "is_current", server_default=None)


def downgrade() -> None:
    op.drop_index("ix_schedules_is_current", table_name="schedules")
    op.drop_column("schedules", "is_current")
