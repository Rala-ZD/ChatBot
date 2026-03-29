from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, Index, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.models.enums import SessionEndReason, SessionStatus


class Session(Base):
    __tablename__ = "sessions"
    __table_args__ = (
        Index("ix_sessions_status_started_at", "status", "started_at"),
        Index("ix_sessions_user1_id_status", "user1_id", "status"),
        Index("ix_sessions_user2_id_status", "user2_id", "status"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    user1_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    user2_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    status: Mapped[SessionStatus] = mapped_column(
        Enum(SessionStatus, native_enum=False, length=32),
        nullable=False,
        default=SessionStatus.ACTIVE,
    )
    end_reason: Mapped[SessionEndReason | None] = mapped_column(
        Enum(SessionEndReason, native_enum=False, length=64),
        nullable=True,
    )
    exported_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
