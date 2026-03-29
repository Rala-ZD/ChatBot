from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import BigInteger, Boolean, Enum, Integer, JSON, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin
from app.db.models.enums import Gender, PreferredGender


class User(TimestampMixin, Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    telegram_id: Mapped[int] = mapped_column(BigInteger, unique=True, nullable=False, index=True)
    username: Mapped[str | None] = mapped_column(String(64), nullable=True)
    first_name: Mapped[str | None] = mapped_column(String(128), nullable=True)
    nickname: Mapped[str | None] = mapped_column(String(32), nullable=True)
    age: Mapped[int | None] = mapped_column(Integer, nullable=True)
    gender: Mapped[Gender | None] = mapped_column(
        Enum(Gender, native_enum=False, length=32),
        nullable=True,
    )
    preferred_gender: Mapped[PreferredGender | None] = mapped_column(
        Enum(PreferredGender, native_enum=False, length=32),
        nullable=True,
    )
    interests_json: Mapped[list[str]] = mapped_column(
        JSON().with_variant(JSONB, "postgresql"),
        nullable=False,
        default=list,
    )
    is_registered: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_banned: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_in_chat: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    consent_accepted_at: Mapped[datetime | None] = mapped_column(nullable=True)
    consent_version: Mapped[str | None] = mapped_column(String(32), nullable=True)

    def profile_snapshot(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "telegram_id": self.telegram_id,
            "username": self.username,
            "first_name": self.first_name,
            "nickname": self.nickname,
            "age": self.age,
            "gender": self.gender.value if self.gender else None,
            "preferred_gender": self.preferred_gender.value if self.preferred_gender else None,
            "interests": self.interests_json,
            "is_registered": self.is_registered,
            "is_banned": self.is_banned,
        }
