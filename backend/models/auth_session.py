from datetime import datetime
from uuid import uuid4

from sqlalchemy import DateTime, ForeignKey, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.db.base import Base


class AuthSession(Base):
    __tablename__ = "auth_sessions"

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
    family_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        index=True,
    )
    refresh_token_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    replaced_by_session_id: Mapped[str | None] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("auth_sessions.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    created_by_ip: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_by_user_agent: Mapped[str | None] = mapped_column(String(512), nullable=True)
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_used_ip: Mapped[str | None] = mapped_column(String(64), nullable=True)
    last_used_user_agent: Mapped[str | None] = mapped_column(String(512), nullable=True)
    rotated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    revoke_reason: Mapped[str | None] = mapped_column(String(100), nullable=True)
    refresh_expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )

    user: Mapped["User"] = relationship(back_populates="auth_sessions")
    replaced_by_session: Mapped["AuthSession | None"] = relationship(
        remote_side="AuthSession.id",
        uselist=False,
    )
