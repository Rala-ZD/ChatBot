from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, Index, Integer, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.utils.enums import EndReason, SessionStatus
from app.utils.time import utcnow


class ChatSession(Base):
    __tablename__ = "sessions"
    __table_args__ = (
        Index("ix_sessions_status_started", "status", "started_at"),
        Index("ix_sessions_user1_status", "user1_id", "status"),
        Index("ix_sessions_user2_status", "user2_id", "status"),
        Index(
            "ix_sessions_active_user1",
            "user1_id",
            postgresql_where=text("status = 'active'"),
        ),
        Index(
            "ix_sessions_active_user2",
            "user2_id",
            postgresql_where=text("status = 'active'"),
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user1_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    user2_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    exported_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    status: Mapped[SessionStatus] = mapped_column(
        Enum(SessionStatus, name="session_status_enum", native_enum=False),
        default=SessionStatus.ACTIVE,
        index=True,
    )
    end_reason: Mapped[EndReason | None] = mapped_column(
        Enum(EndReason, name="end_reason_enum", native_enum=False),
        nullable=True,
    )
    ended_by_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )

    user1: Mapped["User"] = relationship(
        back_populates="active_sessions_as_user1",
        foreign_keys=[user1_id],
    )
    user2: Mapped["User"] = relationship(
        back_populates="active_sessions_as_user2",
        foreign_keys=[user2_id],
    )
    messages: Mapped[list["SessionMessage"]] = relationship(
        back_populates="session",
        order_by="SessionMessage.created_at",
    )
    reports: Mapped[list["Report"]] = relationship(back_populates="session")

    def partner_id_for(self, user_id: int) -> int:
        return self.user2_id if self.user1_id == user_id else self.user1_id

