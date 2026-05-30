from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.db.base import Base


class Task(Base):
    __tablename__ = "tasks"

    id: Mapped[str] = mapped_column(String(255), primary_key=True)
    user_id: Mapped[str] = mapped_column(
        String(255),
        ForeignKey("users.id", ondelete="CASCADE"),
        index=True,
    )

    title: Mapped[str] = mapped_column(String(255))
    description: Mapped[str | None] = mapped_column(String, nullable=True)

    duration_minutes: Mapped[int] = mapped_column(Integer)
    priority: Mapped[int] = mapped_column(Integer, default=3)

    category: Mapped[str | None] = mapped_column(String(50), nullable=True)
    energy_required: Mapped[str | None] = mapped_column(String(20), nullable=True)
    status: Mapped[str] = mapped_column(String(30), default="active")

    deadline: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    earliest_start: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    latest_end: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    fixed_start: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    is_mandatory: Mapped[bool] = mapped_column(Boolean, default=True)
    is_fixed: Mapped[bool] = mapped_column(Boolean, default=False)
    allow_splitting: Mapped[bool] = mapped_column(Boolean, default=False)
    min_split_part_minutes: Mapped[int | None] = mapped_column(Integer, nullable=True)

    preferred_windows: Mapped[list[dict] | None] = mapped_column(JSONB, nullable=True)
    allowed_windows: Mapped[list[dict] | None] = mapped_column(JSONB, nullable=True)
    constraints: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    llm_metadata: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    user: Mapped["User"] = relationship(back_populates="tasks")
    schedule_items: Mapped[list["ScheduledTask"]] = relationship(
        back_populates="task",
        cascade="all, delete-orphan",
    )
    feedback_items: Mapped[list["Feedback"]] = relationship(back_populates="task")

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )
