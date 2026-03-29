from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.utils.enums import PointPurchaseStatus
from app.utils.time import utcnow


class PointPurchase(Base):
    __tablename__ = "point_purchases"
    __table_args__ = (
        Index("ix_point_purchases_user_status", "user_id", "status"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    package_code: Mapped[str] = mapped_column(String(32), nullable=False)
    points_amount: Mapped[int] = mapped_column(Integer, nullable=False)
    total_amount_minor: Mapped[int] = mapped_column(Integer, nullable=False)
    currency: Mapped[str] = mapped_column(String(8), nullable=False)
    invoice_payload: Mapped[str] = mapped_column(String(128), unique=True, index=True)
    telegram_payment_charge_id: Mapped[str | None] = mapped_column(String(255), unique=True, nullable=True)
    provider_payment_charge_id: Mapped[str | None] = mapped_column(String(255), unique=True, nullable=True)
    status: Mapped[PointPurchaseStatus] = mapped_column(
        Enum(PointPurchaseStatus, name="point_purchase_status_enum", native_enum=False),
        default=PointPurchaseStatus.PENDING,
        nullable=False,
        index=True,
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    credited_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    user: Mapped["User"] = relationship(
        back_populates="point_purchases",
        foreign_keys=[user_id],
    )
