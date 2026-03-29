from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, Index, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.models.enums import QueueStatus


class WaitingQueue(Base):
    __tablename__ = "waiting_queue"
    __table_args__ = (
        Index("ix_waiting_queue_status_joined_at", "status", "joined_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    joined_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    status: Mapped[QueueStatus] = mapped_column(
        Enum(QueueStatus, native_enum=False, length=32),
        nullable=False,
        default=QueueStatus.WAITING,
    )
