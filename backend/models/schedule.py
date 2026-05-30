from datetime import datetime
from uuid import uuid4

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.db.base import Base


class AvailabilityWindow(Base):
    __tablename__ = "availability_windows"

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        primary_key=True,
        default=lambda: str(uuid4()),
    )
    user_id: Mapped[str] = mapped_column(
        String(255),
        ForeignKey("users.id", ondelete="CASCADE"),
        index=True,
    )
    schedule_id: Mapped[str | None] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("schedules.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    title: Mapped[str | None] = mapped_column(String(255), nullable=True)
    start_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    end_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    is_recurring: Mapped[bool] = mapped_column(Boolean, default=False)
    recurrence_rule: Mapped[str | None] = mapped_column(String(255), nullable=True)
    source: Mapped[str] = mapped_column(String(50), default="manual")

    user: Mapped["User"] = relationship(back_populates="availability_windows")
    schedule: Mapped["Schedule | None"] = relationship(back_populates="availability_windows")

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )


class BusyInterval(Base):
    __tablename__ = "busy_intervals"

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        primary_key=True,
        default=lambda: str(uuid4()),
    )
    user_id: Mapped[str] = mapped_column(
        String(255),
        ForeignKey("users.id", ondelete="CASCADE"),
        index=True,
    )
    schedule_id: Mapped[str | None] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("schedules.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    title: Mapped[str] = mapped_column(String(255))
    start_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    end_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    source: Mapped[str] = mapped_column(String(50), default="calendar")
    external_event_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    payload: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    user: Mapped["User"] = relationship(back_populates="busy_intervals")
    schedule: Mapped["Schedule | None"] = relationship(back_populates="busy_intervals")

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )


class Schedule(Base):
    __tablename__ = "schedules"

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        primary_key=True,
        default=lambda: str(uuid4()),
    )
    user_id: Mapped[str] = mapped_column(
        String(255),
        ForeignKey("users.id", ondelete="CASCADE"),
        index=True,
    )
    planning_start: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    planning_end: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    slot_minutes: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(30))
    is_current: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    selected_variant_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    source_request: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    profile_context: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    schedule_metadata: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    user: Mapped["User"] = relationship(back_populates="schedules")
    availability_windows: Mapped[list["AvailabilityWindow"]] = relationship(
        back_populates="schedule",
        cascade="all, delete-orphan",
    )
    busy_intervals: Mapped[list["BusyInterval"]] = relationship(
        back_populates="schedule",
        cascade="all, delete-orphan",
    )
    scheduled_tasks: Mapped[list["ScheduledTask"]] = relationship(
        back_populates="schedule",
        cascade="all, delete-orphan",
    )
    feedback_items: Mapped[list["Feedback"]] = relationship(back_populates="schedule")

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )


class ScheduledTask(Base):
    __tablename__ = "scheduled_tasks"

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        primary_key=True,
        default=lambda: str(uuid4()),
    )
    schedule_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("schedules.id", ondelete="CASCADE"),
        index=True,
    )
    task_id: Mapped[str] = mapped_column(
        String(255),
        ForeignKey("tasks.id", ondelete="CASCADE"),
        index=True,
    )
    variant_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    title: Mapped[str] = mapped_column(String(255))
    start_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    end_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    duration_minutes: Mapped[int] = mapped_column(Integer)
    priority: Mapped[int] = mapped_column(Integer)
    is_mandatory: Mapped[bool] = mapped_column(Boolean, default=False)
    split_part_index: Mapped[int | None] = mapped_column(Integer, nullable=True)
    split_part_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    payload: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    schedule: Mapped["Schedule"] = relationship(back_populates="scheduled_tasks")
    task: Mapped["Task"] = relationship(back_populates="schedule_items")

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )
