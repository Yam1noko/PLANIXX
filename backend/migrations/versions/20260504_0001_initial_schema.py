"""initial schema

Revision ID: 20260504_0001
Revises:
Create Date: 2026-05-04 15:55:00
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision = "20260504_0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.String(length=255), primary_key=True, nullable=False),
        sa.Column("email", sa.String(length=255), unique=True, nullable=True),
        sa.Column("timezone", sa.String(length=64), nullable=True),
        sa.Column("locale", sa.String(length=32), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )

    op.create_table(
        "user_profiles",
        sa.Column("user_id", sa.String(length=255), sa.ForeignKey("users.id", ondelete="CASCADE"), primary_key=True, nullable=False),
        sa.Column("profile_data", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("ix_user_profiles_user_id", "user_profiles", ["user_id"])

    op.create_table(
        "tasks",
        sa.Column("id", sa.String(length=255), primary_key=True, nullable=False),
        sa.Column("user_id", sa.String(length=255), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("description", sa.String(), nullable=True),
        sa.Column("duration_minutes", sa.Integer(), nullable=False),
        sa.Column("priority", sa.Integer(), nullable=False),
        sa.Column("category", sa.String(length=50), nullable=True),
        sa.Column("energy_required", sa.String(length=20), nullable=True),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("deadline", sa.DateTime(timezone=True), nullable=True),
        sa.Column("earliest_start", sa.DateTime(timezone=True), nullable=True),
        sa.Column("latest_end", sa.DateTime(timezone=True), nullable=True),
        sa.Column("fixed_start", sa.DateTime(timezone=True), nullable=True),
        sa.Column("is_mandatory", sa.Boolean(), nullable=False),
        sa.Column("is_fixed", sa.Boolean(), nullable=False),
        sa.Column("preferred_windows", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("allowed_windows", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("constraints", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("llm_metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("ix_tasks_user_id", "tasks", ["user_id"])

    op.create_table(
        "schedules",
        sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True, nullable=False),
        sa.Column("user_id", sa.String(length=255), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("planning_start", sa.DateTime(timezone=True), nullable=False),
        sa.Column("planning_end", sa.DateTime(timezone=True), nullable=False),
        sa.Column("slot_minutes", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("selected_variant_id", sa.Integer(), nullable=True),
        sa.Column("source_request", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("profile_context", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("schedule_metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("ix_schedules_user_id", "schedules", ["user_id"])

    op.create_table(
        "availability_windows",
        sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True, nullable=False),
        sa.Column("user_id", sa.String(length=255), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("schedule_id", postgresql.UUID(as_uuid=False), sa.ForeignKey("schedules.id", ondelete="SET NULL"), nullable=True),
        sa.Column("title", sa.String(length=255), nullable=True),
        sa.Column("start_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("end_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("is_recurring", sa.Boolean(), nullable=False),
        sa.Column("recurrence_rule", sa.String(length=255), nullable=True),
        sa.Column("source", sa.String(length=50), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("ix_availability_windows_user_id", "availability_windows", ["user_id"])
    op.create_index("ix_availability_windows_schedule_id", "availability_windows", ["schedule_id"])

    op.create_table(
        "busy_intervals",
        sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True, nullable=False),
        sa.Column("user_id", sa.String(length=255), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("schedule_id", postgresql.UUID(as_uuid=False), sa.ForeignKey("schedules.id", ondelete="SET NULL"), nullable=True),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("start_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("end_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("source", sa.String(length=50), nullable=False),
        sa.Column("external_event_id", sa.String(length=255), nullable=True),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("ix_busy_intervals_user_id", "busy_intervals", ["user_id"])
    op.create_index("ix_busy_intervals_schedule_id", "busy_intervals", ["schedule_id"])

    op.create_table(
        "scheduled_tasks",
        sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True, nullable=False),
        sa.Column("schedule_id", postgresql.UUID(as_uuid=False), sa.ForeignKey("schedules.id", ondelete="CASCADE"), nullable=False),
        sa.Column("task_id", sa.String(length=255), sa.ForeignKey("tasks.id", ondelete="CASCADE"), nullable=False),
        sa.Column("variant_id", sa.Integer(), nullable=True),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("start_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("end_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("duration_minutes", sa.Integer(), nullable=False),
        sa.Column("priority", sa.Integer(), nullable=False),
        sa.Column("is_mandatory", sa.Boolean(), nullable=False),
        sa.Column("split_part_index", sa.Integer(), nullable=True),
        sa.Column("split_part_count", sa.Integer(), nullable=True),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("ix_scheduled_tasks_schedule_id", "scheduled_tasks", ["schedule_id"])
    op.create_index("ix_scheduled_tasks_task_id", "scheduled_tasks", ["task_id"])

    op.create_table(
        "feedback",
        sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True, nullable=False),
        sa.Column("user_id", sa.String(length=255), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("schedule_id", postgresql.UUID(as_uuid=False), sa.ForeignKey("schedules.id", ondelete="SET NULL"), nullable=True),
        sa.Column("task_id", sa.String(length=255), sa.ForeignKey("tasks.id", ondelete="SET NULL"), nullable=True),
        sa.Column("feedback_type", sa.String(length=50), nullable=False),
        sa.Column("rating", sa.Integer(), nullable=True),
        sa.Column("comment", sa.String(), nullable=True),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("ix_feedback_user_id", "feedback", ["user_id"])
    op.create_index("ix_feedback_schedule_id", "feedback", ["schedule_id"])
    op.create_index("ix_feedback_task_id", "feedback", ["task_id"])


def downgrade() -> None:
    op.drop_index("ix_feedback_task_id", table_name="feedback")
    op.drop_index("ix_feedback_schedule_id", table_name="feedback")
    op.drop_index("ix_feedback_user_id", table_name="feedback")
    op.drop_table("feedback")

    op.drop_index("ix_scheduled_tasks_task_id", table_name="scheduled_tasks")
    op.drop_index("ix_scheduled_tasks_schedule_id", table_name="scheduled_tasks")
    op.drop_table("scheduled_tasks")

    op.drop_index("ix_busy_intervals_schedule_id", table_name="busy_intervals")
    op.drop_index("ix_busy_intervals_user_id", table_name="busy_intervals")
    op.drop_table("busy_intervals")

    op.drop_index("ix_availability_windows_schedule_id", table_name="availability_windows")
    op.drop_index("ix_availability_windows_user_id", table_name="availability_windows")
    op.drop_table("availability_windows")

    op.drop_index("ix_schedules_user_id", table_name="schedules")
    op.drop_table("schedules")

    op.drop_index("ix_tasks_user_id", table_name="tasks")
    op.drop_table("tasks")

    op.drop_index("ix_user_profiles_user_id", table_name="user_profiles")
    op.drop_table("user_profiles")

    op.drop_table("users")
