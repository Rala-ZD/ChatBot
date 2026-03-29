from __future__ import annotations

from pydantic import BaseModel, Field, field_validator

from app.utils.enums import Gender, PreferredGender
from app.utils.text import normalize_interests


class RegistrationPayload(BaseModel):
    age: int = Field(ge=13, le=100)
    gender: Gender
    nickname: str | None = Field(default=None, max_length=32)
    preferred_gender: PreferredGender = PreferredGender.ANY
    interests: list[str] = Field(default_factory=list)
    consented: bool = True

    @field_validator("nickname")
    @classmethod
    def normalize_nickname(cls, value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = value.strip()
        return cleaned or None

    @field_validator("interests", mode="before")
    @classmethod
    def normalize_interest_input(cls, value: object) -> list[str]:
        if value is None:
            return []
        if isinstance(value, str):
            return normalize_interests(value)
        if isinstance(value, list):
            normalized = [str(item).strip().lower() for item in value if str(item).strip()]
            return normalize_interests(",".join(normalized))
        raise TypeError("Invalid interests payload")


class UserProfileRead(BaseModel):
    id: int
    telegram_id: int
    nickname: str | None
    age: int | None
    gender: str | None
    preferred_gender: str | None
    interests: list[str]
    is_registered: bool
    is_banned: bool

    model_config = {"from_attributes": True}

