"""add agent conversation and memory tables

Revision ID: 20260515_0006
Revises: 20260506_0005
Create Date: 2026-05-15 22:30:00
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20260515_0006"
down_revision = "20260506_0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "conversations",
        sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True, nullable=False),
        sa.Column("user_id", sa.String(length=255), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=True),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("model_name", sa.String(length=100), nullable=True),
        sa.Column("system_prompt", sa.Text(), nullable=True),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("context_data", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("last_message_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("ix_conversations_user_id", "conversations", ["user_id"])
    op.create_index("ix_conversations_status", "conversations", ["status"])
    op.create_index("ix_conversations_last_message_at", "conversations", ["last_message_at"])

    op.create_table(
        "conversation_messages",
        sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True, nullable=False),
        sa.Column("conversation_id", postgresql.UUID(as_uuid=False), sa.ForeignKey("conversations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", sa.String(length=255), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("role", sa.String(length=30), nullable=False),
        sa.Column("message_type", sa.String(length=30), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("tool_name", sa.String(length=100), nullable=True),
        sa.Column("tool_call_id", sa.String(length=255), nullable=True),
        sa.Column("message_metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    op.create_index(
        "ix_conversation_messages_conversation_id",
        "conversation_messages",
        ["conversation_id"],
    )
    op.create_index("ix_conversation_messages_user_id", "conversation_messages", ["user_id"])
    op.create_index("ix_conversation_messages_role", "conversation_messages", ["role"])

    op.create_table(
        "task_drafts",
        sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True, nullable=False),
        sa.Column("user_id", sa.String(length=255), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("conversation_id", postgresql.UUID(as_uuid=False), sa.ForeignKey("conversations.id", ondelete="SET NULL"), nullable=True),
        sa.Column("source_message_id", postgresql.UUID(as_uuid=False), sa.ForeignKey("conversation_messages.id", ondelete="SET NULL"), nullable=True),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("raw_text", sa.Text(), nullable=False),
        sa.Column("draft_data", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("model_name", sa.String(length=100), nullable=True),
        sa.Column("confidence_score", sa.Float(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("ix_task_drafts_user_id", "task_drafts", ["user_id"])
    op.create_index("ix_task_drafts_conversation_id", "task_drafts", ["conversation_id"])
    op.create_index("ix_task_drafts_source_message_id", "task_drafts", ["source_message_id"])
    op.create_index("ix_task_drafts_status", "task_drafts", ["status"])

    op.create_table(
        "user_task_patterns",
        sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True, nullable=False),
        sa.Column("user_id", sa.String(length=255), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("pattern_type", sa.String(length=50), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("pattern_data", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("confidence_score", sa.Float(), nullable=True),
        sa.Column("source", sa.String(length=50), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("last_observed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("ix_user_task_patterns_user_id", "user_task_patterns", ["user_id"])
    op.create_index("ix_user_task_patterns_pattern_type", "user_task_patterns", ["pattern_type"])
    op.create_index("ix_user_task_patterns_is_active", "user_task_patterns", ["is_active"])

    op.create_table(
        "user_memories",
        sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True, nullable=False),
        sa.Column("user_id", sa.String(length=255), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("memory_type", sa.String(length=50), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("memory_data", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("confidence_score", sa.Float(), nullable=True),
        sa.Column("importance_score", sa.Float(), nullable=True),
        sa.Column("source", sa.String(length=50), nullable=False),
        sa.Column("last_accessed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("superseded_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("ix_user_memories_user_id", "user_memories", ["user_id"])
    op.create_index("ix_user_memories_memory_type", "user_memories", ["memory_type"])

    op.create_table(
        "memory_candidates",
        sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True, nullable=False),
        sa.Column("user_id", sa.String(length=255), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("conversation_id", postgresql.UUID(as_uuid=False), sa.ForeignKey("conversations.id", ondelete="SET NULL"), nullable=True),
        sa.Column("source_message_id", postgresql.UUID(as_uuid=False), sa.ForeignKey("conversation_messages.id", ondelete="SET NULL"), nullable=True),
        sa.Column("accepted_memory_id", postgresql.UUID(as_uuid=False), sa.ForeignKey("user_memories.id", ondelete="SET NULL"), nullable=True),
        sa.Column("candidate_type", sa.String(length=50), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("candidate_data", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("confidence_score", sa.Float(), nullable=True),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("rejection_reason", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("ix_memory_candidates_user_id", "memory_candidates", ["user_id"])
    op.create_index("ix_memory_candidates_conversation_id", "memory_candidates", ["conversation_id"])
    op.create_index("ix_memory_candidates_source_message_id", "memory_candidates", ["source_message_id"])
    op.create_index("ix_memory_candidates_accepted_memory_id", "memory_candidates", ["accepted_memory_id"])
    op.create_index("ix_memory_candidates_candidate_type", "memory_candidates", ["candidate_type"])
    op.create_index("ix_memory_candidates_status", "memory_candidates", ["status"])


def downgrade() -> None:
    op.drop_index("ix_memory_candidates_status", table_name="memory_candidates")
    op.drop_index("ix_memory_candidates_candidate_type", table_name="memory_candidates")
    op.drop_index("ix_memory_candidates_accepted_memory_id", table_name="memory_candidates")
    op.drop_index("ix_memory_candidates_source_message_id", table_name="memory_candidates")
    op.drop_index("ix_memory_candidates_conversation_id", table_name="memory_candidates")
    op.drop_index("ix_memory_candidates_user_id", table_name="memory_candidates")
    op.drop_table("memory_candidates")

    op.drop_index("ix_user_memories_memory_type", table_name="user_memories")
    op.drop_index("ix_user_memories_user_id", table_name="user_memories")
    op.drop_table("user_memories")

    op.drop_index("ix_user_task_patterns_is_active", table_name="user_task_patterns")
    op.drop_index("ix_user_task_patterns_pattern_type", table_name="user_task_patterns")
    op.drop_index("ix_user_task_patterns_user_id", table_name="user_task_patterns")
    op.drop_table("user_task_patterns")

    op.drop_index("ix_task_drafts_status", table_name="task_drafts")
    op.drop_index("ix_task_drafts_source_message_id", table_name="task_drafts")
    op.drop_index("ix_task_drafts_conversation_id", table_name="task_drafts")
    op.drop_index("ix_task_drafts_user_id", table_name="task_drafts")
    op.drop_table("task_drafts")

    op.drop_index("ix_conversation_messages_role", table_name="conversation_messages")
    op.drop_index("ix_conversation_messages_user_id", table_name="conversation_messages")
    op.drop_index("ix_conversation_messages_conversation_id", table_name="conversation_messages")
    op.drop_table("conversation_messages")

    op.drop_index("ix_conversations_last_message_at", table_name="conversations")
    op.drop_index("ix_conversations_status", table_name="conversations")
    op.drop_index("ix_conversations_user_id", table_name="conversations")
    op.drop_table("conversations")
