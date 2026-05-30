from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.db.base import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(255), primary_key=True)
    username: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    email: Mapped[str | None] = mapped_column(String(255), unique=True, nullable=True)
    password_hash: Mapped[str | None] = mapped_column(String(255), nullable=True)
    is_active: Mapped[bool] = mapped_column(default=True)
    timezone: Mapped[str | None] = mapped_column(String(64), nullable=True)
    locale: Mapped[str | None] = mapped_column(String(32), nullable=True)
    last_login_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    profile: Mapped["UserProfile | None"] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
        uselist=False,
    )
    tasks: Mapped[list["Task"]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
    )
    availability_windows: Mapped[list["AvailabilityWindow"]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
    )
    busy_intervals: Mapped[list["BusyInterval"]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
    )
    schedules: Mapped[list["Schedule"]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
    )
    feedback_items: Mapped[list["Feedback"]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
    )
    auth_sessions: Mapped[list["AuthSession"]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
    )
    conversations: Mapped[list["Conversation"]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
    )
    conversation_messages: Mapped[list["ConversationMessage"]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
    )
    task_drafts: Mapped[list["TaskDraft"]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
    )
    task_patterns: Mapped[list["UserTaskPattern"]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
    )
    memories: Mapped[list["UserMemory"]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
    )
    memory_candidates: Mapped[list["MemoryCandidate"]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )


class UserProfile(Base):
    __tablename__ = "user_profiles"

    user_id: Mapped[str] = mapped_column(
        String(255),
        ForeignKey("users.id", ondelete="CASCADE"),
        primary_key=True,
        index=True,
    )
    profile_data: Mapped[dict] = mapped_column(JSONB)

    user: Mapped["User"] = relationship(back_populates="profile")

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )
