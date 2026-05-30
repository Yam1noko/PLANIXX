"""add task-level splitting fields

Revision ID: 20260506_0005
Revises: 20260505_0004
Create Date: 2026-05-06 00:00:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "20260506_0005"
down_revision: Union[str, Sequence[str], None] = "20260505_0004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "tasks",
        sa.Column(
            "allow_splitting",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
    )
    op.add_column(
        "tasks",
        sa.Column("min_split_part_minutes", sa.Integer(), nullable=True),
    )
    op.alter_column("tasks", "allow_splitting", server_default=None)


def downgrade() -> None:
    op.drop_column("tasks", "min_split_part_minutes")
    op.drop_column("tasks", "allow_splitting")
