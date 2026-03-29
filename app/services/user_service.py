from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta

from aiogram.types import User as TelegramUser
from redis.asyncio import Redis

from app.config import Settings
from app.db.models.user import User
from app.db.repositories.user_repository import UserRepository
from app.schemas.user import RegistrationPayload
from app.services.exceptions import ValidationError
from app.utils.referral import extract_referral_code
from app.utils.text import normalize_interests
from app.utils.time import utcnow


REFERRAL_REWARD_POINTS = 5
VIP_COST_POINTS = 10
VIP_DURATION = timedelta(days=1)
LAST_ACTIVE_TTL_SECONDS = 300


@dataclass(slots=True)
class UserAccessResult:
    user: User
    created: bool


class UserService:
    def __init__(self, user_repository: UserRepository, settings: Settings, redis: Redis) -> None:
        self.user_repository = user_repository
        self.settings = settings
        self.redis = redis

    async def ensure_telegram_user(self, telegram_user: TelegramUser) -> UserAccessResult:
        touch_last_active = await self._should_touch_last_active(telegram_user.id)
        user, created, changed = await self.user_repository.upsert_from_telegram(
            telegram_user,
            touch_last_active=touch_last_active,
        )
        if changed:
            await self.user_repository.session.commit()
        return UserAccessResult(user=user, created=created)

    async def _should_touch_last_active(self, telegram_id: int) -> bool:
        key = f"user:last_active_gate:{telegram_id}"
        return bool(await self.redis.set(key, "1", ex=LAST_ACTIVE_TTL_SECONDS, nx=True))

    def parse_age(self, raw_value: str) -> int:
        try:
            age = int(raw_value.strip())
        except ValueError as exc:
            raise ValidationError("Please enter your age as a number.") from exc
        if age < self.settings.minimum_age:
            raise ValidationError(
                f"You must be at least {self.settings.minimum_age} to use this bot."
            )
        if age > 100:
            raise ValidationError("Please enter a valid age.")
        return age

    def normalize_nickname(self, raw_value: str) -> str | None:
        cleaned = raw_value.strip()
        if not cleaned:
            return None
        if len(cleaned) > 32:
            raise ValidationError("Nickname must be 32 characters or fewer.")
        return cleaned

    def normalize_interests(self, raw_value: str) -> list[str]:
        try:
            return normalize_interests(raw_value)
        except ValueError as exc:
            raise ValidationError(str(exc)) from exc

    async def register_user(self, user: User, payload: RegistrationPayload) -> User:
        was_registered = user.is_registered
        user.age = payload.age
        user.gender = payload.gender
        user.nickname = payload.nickname
        user.preferred_gender = payload.preferred_gender
        user.interests_json = payload.interests
        user.is_registered = True
        user.consented_at = utcnow()
        if not was_registered and user.referred_by_user_id is not None:
            inviter = await self.user_repository.get_by_id(user.referred_by_user_id)
            if inviter is not None:
                inviter.points_balance += REFERRAL_REWARD_POINTS
                await self.user_repository.save(inviter)
        await self.user_repository.save(user)
        await self.user_repository.session.commit()
        return user

    async def update_profile(self, user: User, **updates: object) -> User:
        for field, value in updates.items():
            setattr(user, field, value)
        user.updated_at = utcnow()
        await self.user_repository.save(user)
        await self.user_repository.session.commit()
        return user

    def ensure_registered(self, user: User) -> None:
        if not user.is_registered:
            raise ValidationError("Finish setup with /start first.")

    async def apply_referral_code_if_eligible(
        self,
        user: User,
        start_argument: str | None,
        *,
        is_new_user: bool,
    ) -> None:
        referral_code = extract_referral_code(start_argument)
        if not is_new_user or not referral_code or user.referred_by_user_id is not None:
            return

        inviter = await self.user_repository.get_by_referral_code(referral_code)
        if inviter is None or inviter.id == user.id:
            return

        user.referred_by_user_id = inviter.id
        await self.user_repository.save(user)
        await self.user_repository.session.commit()

    async def purchase_vip(self, user: User) -> User:
        self.ensure_registered(user)
        if user.points_balance < VIP_COST_POINTS:
            raise ValidationError("You need 10 points to unlock premium.")

        user.points_balance -= VIP_COST_POINTS
        now = utcnow()
        vip_start = user.vip_until if user.vip_until and user.vip_until > now else now
        user.vip_until = vip_start + VIP_DURATION
        await self.user_repository.save(user)
        await self.user_repository.session.commit()
        return user

    def is_vip_active(self, user: User) -> bool:
        return user.has_active_vip()
