from __future__ import annotations

from decimal import Decimal
from datetime import datetime
from typing import Any

from sqlalchemy import BigInteger, Boolean, CheckConstraint, DateTime, Enum, ForeignKey, Integer, JSON, Numeric, String, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.utils.enums import Gender, PreferredGender
from app.utils.time import utcnow


class User(Base):
    __tablename__ = "users"
    __table_args__ = (
        CheckConstraint(
            "rating_score IS NULL OR (rating_score >= -5.0 AND rating_score <= 5.0)",
            name="rating_score_range",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    telegram_id: Mapped[int] = mapped_column(BigInteger, unique=True, index=True)
    username: Mapped[str | None] = mapped_column(String(255), nullable=True)
    first_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    nickname: Mapped[str | None] = mapped_column(String(32), nullable=True)
    referral_code: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    referred_by_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    points_balance: Mapped[int] = mapped_column(Integer, default=0)
    vip_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    age: Mapped[int | None] = mapped_column(Integer, nullable=True)
    gender: Mapped[Gender | None] = mapped_column(
        Enum(Gender, name="gender_enum", native_enum=False),
        nullable=True,
    )
    match_region: Mapped[str | None] = mapped_column(String(32), nullable=True)
    preferred_gender: Mapped[PreferredGender] = mapped_column(
        Enum(PreferredGender, name="preferred_gender_enum", native_enum=False),
        default=PreferredGender.ANY,
    )
    interests_json: Mapped[list[str]] = mapped_column(JSON, default=list)
    rating_score: Mapped[Decimal] = mapped_column(
        Numeric(2, 1),
        default=Decimal("5.0"),
        server_default=text("5.0"),
        nullable=False,
    )
    is_registered: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    is_banned: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    consented_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_active_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    referred_by: Mapped["User | None"] = relationship(
        "User",
        back_populates="referrals",
        foreign_keys=[referred_by_user_id],
        remote_side="User.id",
    )
    referrals: Mapped[list["User"]] = relationship(
        "User",
        back_populates="referred_by",
        foreign_keys="User.referred_by_user_id",
    )
    queue_entries: Mapped[list["WaitingQueueEntry"]] = relationship(back_populates="user")
    reports_made: Mapped[list["Report"]] = relationship(
        back_populates="reporter",
        foreign_keys="Report.reporter_user_id",
    )
    bans: Mapped[list["Ban"]] = relationship(
        back_populates="user",
        foreign_keys="Ban.user_id",
    )
    active_sessions_as_user1: Mapped[list["ChatSession"]] = relationship(
        back_populates="user1",
        foreign_keys="ChatSession.user1_id",
    )
    active_sessions_as_user2: Mapped[list["ChatSession"]] = relationship(
        back_populates="user2",
        foreign_keys="ChatSession.user2_id",
    )
    point_purchases: Mapped[list["PointPurchase"]] = relationship(
        back_populates="user",
        foreign_keys="PointPurchase.user_id",
    )
    ratings_given: Mapped[list["SessionRating"]] = relationship(
        back_populates="from_user",
        foreign_keys="SessionRating.from_user_id",
    )
    ratings_received: Mapped[list["SessionRating"]] = relationship(
        back_populates="to_user",
        foreign_keys="SessionRating.to_user_id",
    )

    def admin_metadata(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "telegram_id": self.telegram_id,
            "username": self.username,
            "first_name": self.first_name,
            "nickname": self.nickname,
            "referral_code": self.referral_code,
            "referred_by_user_id": self.referred_by_user_id,
            "points_balance": self.points_balance,
            "vip_until": self.vip_until.isoformat() if self.vip_until else None,
            "age": self.age,
            "gender": self.gender.value if self.gender else None,
            "match_region": self.match_region,
            "preferred_gender": self.preferred_gender.value if self.preferred_gender else None,
            "interests": self.interests_json,
            "rating_score": float(self.rating_score),
            "is_banned": self.is_banned,
        }

    def has_active_vip(self) -> bool:
        return self.vip_until is not None and self.vip_until > utcnow()

