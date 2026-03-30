from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, Index, Integer, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.utils.enums import SessionRatingValue
from app.utils.time import utcnow


class SessionRating(Base):
    __tablename__ = "session_ratings"
    __table_args__ = (
        UniqueConstraint("session_id", "from_user_id", name="uq_session_ratings_session_from_user"),
        Index("ix_session_ratings_session_id", "session_id"),
        Index("ix_session_ratings_to_user_id", "to_user_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    session_id: Mapped[int] = mapped_column(ForeignKey("sessions.id", ondelete="CASCADE"), nullable=False)
    from_user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    to_user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    value: Mapped[SessionRatingValue] = mapped_column(
        Enum(SessionRatingValue, name="session_rating_value_enum", native_enum=False),
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    session: Mapped["ChatSession"] = relationship(back_populates="ratings")
    from_user: Mapped["User"] = relationship(
        back_populates="ratings_given",
        foreign_keys=[from_user_id],
    )
    to_user: Mapped["User"] = relationship(
        back_populates="ratings_received",
        foreign_keys=[to_user_id],
    )
