from __future__ import annotations

from datetime import UTC, datetime

from aiogram.types import User as TelegramUser
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.config import Settings
from app.db.models import Gender, PreferredGender, User
from app.db.repositories.user_repository import UserRepository
from app.db.session import session_scope
from app.utils.exceptions import ConflictError, UserVisibleError


class UserService:
    def __init__(
        self,
        session_factory: async_sessionmaker,
        settings: Settings,
    ) -> None:
        self.session_factory = session_factory
        self.settings = settings

    async def sync_telegram_user(self, telegram_user: TelegramUser) -> User:
        async with session_scope(self.session_factory) as session:
            repo = UserRepository(session)
            return await repo.get_or_create_by_telegram_identity(
                telegram_id=telegram_user.id,
                username=telegram_user.username,
                first_name=telegram_user.first_name,
            )

    async def get_by_telegram_id(self, telegram_id: int) -> User | None:
        async with session_scope(self.session_factory) as session:
            repo = UserRepository(session)
            return await repo.get_by_telegram_id(telegram_id)

    async def require_registered_user(self, telegram_id: int) -> User:
        user = await self.get_by_telegram_id(telegram_id)
        if user is None or not user.is_registered:
            raise UserVisibleError("Please complete registration before starting a chat.")
        if user.is_banned:
            raise UserVisibleError("Your access is currently restricted. Contact support if you believe this is a mistake.")
        return user

    def validate_age(self, raw_age: str) -> int:
        if not raw_age.strip().isdigit():
            raise UserVisibleError("Enter your age using digits only.")
        age = int(raw_age.strip())
        if age < self.settings.minimum_age:
            raise UserVisibleError(
                f"You must be at least {self.settings.minimum_age} years old to use this bot."
            )
        if age > 99:
            raise UserVisibleError("Please enter a valid age.")
        return age

    def validate_nickname(self, raw_nickname: str) -> str | None:
        value = raw_nickname.strip()
        if not value:
            return None
        if len(value) > self.settings.profile_nickname_max_length:
            raise UserVisibleError(
                f"Nickname must be {self.settings.profile_nickname_max_length} characters or fewer."
            )
        return value

    def validate_interests(self, raw_interests: str) -> list[str]:
        if not raw_interests.strip():
            return []
        parts = []
        for item in raw_interests.split(","):
            normalized = item.strip().lower()
            if not normalized:
                continue
            if len(normalized) > self.settings.profile_interest_max_length:
                raise UserVisibleError(
                    f"Each interest must be {self.settings.profile_interest_max_length} characters or fewer."
                )
            if normalized not in parts:
                parts.append(normalized)
        if len(parts) > self.settings.profile_interests_max_count:
            raise UserVisibleError(
                f"You can save up to {self.settings.profile_interests_max_count} interests."
            )
        return parts

    async def complete_registration(
        self,
        telegram_user: TelegramUser,
        *,
        age: int,
        gender: Gender,
        nickname: str | None,
        preferred_gender: PreferredGender | None,
        interests: list[str],
    ) -> User:
        async with session_scope(self.session_factory) as session:
            repo = UserRepository(session)
            user = await repo.get_or_create_by_telegram_identity(
                telegram_id=telegram_user.id,
                username=telegram_user.username,
                first_name=telegram_user.first_name,
            )
            if user.is_banned:
                raise UserVisibleError("Your access is currently restricted.")
            user.age = age
            user.gender = gender
            user.nickname = nickname
            user.preferred_gender = preferred_gender
            user.interests_json = interests
            user.is_registered = True
            user.consent_accepted_at = datetime.now(UTC)
            user.consent_version = self.settings.consent_version
            return user

    async def update_profile_field(
        self,
        telegram_id: int,
        *,
        field_name: str,
        value: object,
    ) -> User:
        async with session_scope(self.session_factory) as session:
            repo = UserRepository(session)
            user = await repo.get_by_telegram_id(telegram_id)
            if user is None or not user.is_registered:
                raise UserVisibleError("Please complete registration first.")
            if not hasattr(user, field_name):
                raise ConflictError("That profile field cannot be updated.")
            setattr(user, field_name, value)
            return user

    def format_profile(self, user: User) -> str:
        nickname = user.nickname or "Not set"
        preferred = user.preferred_gender.value if user.preferred_gender else "any"
        interests = ", ".join(user.interests_json) if user.interests_json else "None added"
        return (
            "<b>Your profile</b>\n"
            f"Nickname: {nickname}\n"
            f"Age: {user.age or 'Not set'}\n"
            f"Gender: {user.gender.value if user.gender else 'Not set'}\n"
            f"Preferred gender: {preferred}\n"
            f"Interests: {interests}"
        )

    async def mark_banned_state(self, user_id: int, is_banned: bool) -> None:
        async with session_scope(self.session_factory) as session:
            repo = UserRepository(session)
            user = await repo.get_by_id(user_id)
            if user is None:
                raise UserVisibleError("User not found.")
            user.is_banned = is_banned
