from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, Index, Integer, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.utils.enums import QueueStatus
from app.utils.time import utcnow


class WaitingQueueEntry(Base):
    __tablename__ = "waiting_queue"
    __table_args__ = (
        Index(
            "uq_waiting_queue_user_active",
            "user_id",
            unique=True,
            postgresql_where=text("status = 'waiting'"),
        ),
        Index("ix_waiting_queue_status_joined", "status", "joined_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    joined_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    status: Mapped[QueueStatus] = mapped_column(
        Enum(QueueStatus, name="queue_status_enum", native_enum=False),
        default=QueueStatus.WAITING,
        index=True,
    )
    match_attempts: Mapped[int] = mapped_column(Integer, default=0)

    user: Mapped["User"] = relationship(back_populates="queue_entries")

