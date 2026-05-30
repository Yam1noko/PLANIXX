"""add usernames and refresh sessions

Revision ID: 20260504_0003
Revises: 20260504_0002
Create Date: 2026-05-04 19:05:00
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20260504_0003"
down_revision = "20260504_0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("users", sa.Column("username", sa.String(length=32), nullable=True))

    op.execute(
        """
        UPDATE users
        SET username = CASE
            WHEN email IS NOT NULL AND split_part(email, '@', 1) <> ''
                THEN CASE
                    WHEN substring(
                        lower(regexp_replace(split_part(email, '@', 1), '[^a-zA-Z0-9._-]+', '_', 'g'))
                        from 1 for 24
                    ) <> ''
                    THEN substring(
                        lower(regexp_replace(split_part(email, '@', 1), '[^a-zA-Z0-9._-]+', '_', 'g'))
                        from 1 for 24
                    ) || '_' || substring(md5(id) from 1 for 6)
                    ELSE 'user_' || substring(md5(id) from 1 for 12)
                END
            ELSE 'user_' || substring(md5(id) from 1 for 12)
        END
        WHERE username IS NULL
        """
    )

    op.alter_column("users", "username", nullable=False)
    op.create_index("ix_users_username", "users", ["username"], unique=True)

    op.create_table(
        "auth_sessions",
        sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True, nullable=False),
        sa.Column("user_id", sa.String(length=255), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("family_id", postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column("refresh_token_hash", sa.String(length=64), nullable=False),
        sa.Column("replaced_by_session_id", postgresql.UUID(as_uuid=False), sa.ForeignKey("auth_sessions.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_by_ip", sa.String(length=64), nullable=True),
        sa.Column("created_by_user_agent", sa.String(length=512), nullable=True),
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_used_ip", sa.String(length=64), nullable=True),
        sa.Column("last_used_user_agent", sa.String(length=512), nullable=True),
        sa.Column("rotated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoke_reason", sa.String(length=100), nullable=True),
        sa.Column("refresh_expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("ix_auth_sessions_user_id", "auth_sessions", ["user_id"])
    op.create_index("ix_auth_sessions_family_id", "auth_sessions", ["family_id"])
    op.create_index("ix_auth_sessions_refresh_token_hash", "auth_sessions", ["refresh_token_hash"], unique=True)
    op.create_index("ix_auth_sessions_replaced_by_session_id", "auth_sessions", ["replaced_by_session_id"])


def downgrade() -> None:
    op.drop_index("ix_auth_sessions_replaced_by_session_id", table_name="auth_sessions")
    op.drop_index("ix_auth_sessions_refresh_token_hash", table_name="auth_sessions")
    op.drop_index("ix_auth_sessions_family_id", table_name="auth_sessions")
    op.drop_index("ix_auth_sessions_user_id", table_name="auth_sessions")
    op.drop_table("auth_sessions")

    op.drop_index("ix_users_username", table_name="users")
    op.drop_column("users", "username")
