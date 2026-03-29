from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import BigInteger, DateTime, Enum, ForeignKey, Index, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.utils.enums import DeliveryStatus, MessageType
from app.utils.time import utcnow


class SessionMessage(Base):
    __tablename__ = "session_messages"
    __table_args__ = (
        Index("ix_session_messages_session_created", "session_id", "created_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    session_id: Mapped[int] = mapped_column(ForeignKey("sessions.id", ondelete="CASCADE"), index=True)
    sender_user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    sender_chat_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    source_message_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    message_type: Mapped[MessageType] = mapped_column(
        Enum(MessageType, name="message_type_enum", native_enum=False),
        nullable=False,
    )
    telegram_message_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    relay_chat_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    relay_message_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    delivery_status: Mapped[DeliveryStatus] = mapped_column(
        Enum(DeliveryStatus, name="delivery_status_enum", native_enum=False),
        default=DeliveryStatus.DELIVERED,
    )
    text_content: Mapped[str | None] = mapped_column(Text, nullable=True)
    caption: Mapped[str | None] = mapped_column(Text, nullable=True)
    file_id: Mapped[str | None] = mapped_column(String(512), nullable=True)
    file_unique_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    error_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    metadata_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    session: Mapped["ChatSession"] = relationship(back_populates="messages")

