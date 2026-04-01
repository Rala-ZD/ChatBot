from __future__ import annotations

from decimal import Decimal

from aiogram.types import User as TelegramUser
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.user import User
from app.utils.referral import generate_referral_code
from app.utils.time import utcnow


class UserRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_by_id(self, user_id: int) -> User | None:
        return await self.session.get(User, user_id)

    async def get_by_id_for_update(self, user_id: int) -> User | None:
        result = await self.session.execute(
            select(User).where(User.id == user_id).with_for_update()
        )
        return result.scalar_one_or_none()

    async def get_by_telegram_id(self, telegram_id: int) -> User | None:
        result = await self.session.execute(select(User).where(User.telegram_id == telegram_id))
        return result.scalar_one_or_none()

    async def get_by_referral_code(self, referral_code: str) -> User | None:
        result = await self.session.execute(
            select(User).where(User.referral_code == referral_code.upper())
        )
        return result.scalar_one_or_none()

    async def upsert_from_telegram(
        self,
        telegram_user: TelegramUser,
        *,
        touch_last_active: bool,
    ) -> tuple[User, bool, bool]:
        user = await self.get_by_telegram_id(telegram_user.id)
        now = utcnow()
        created = False
        changed = False
        if user is None:
            user = User(
                telegram_id=telegram_user.id,
                username=telegram_user.username,
                first_name=telegram_user.first_name,
                referral_code=await self.generate_unique_referral_code(),
                points_balance=0,
                rating_score=Decimal("5.0"),
                last_active_at=now,
            )
            self.session.add(user)
            created = True
            changed = True
        else:
            if user.username != telegram_user.username:
                user.username = telegram_user.username
                changed = True
            if user.first_name != telegram_user.first_name:
                user.first_name = telegram_user.first_name
                changed = True
            if touch_last_active:
                user.last_active_at = now
                changed = True
            if not user.referral_code:
                user.referral_code = await self.generate_unique_referral_code()
                changed = True
        if changed:
            await self.session.flush()
        return user, created, changed

    async def save(self, user: User) -> User:
        self.session.add(user)
        await self.session.flush()
        return user

    async def generate_unique_referral_code(self) -> str:
        while True:
            code = generate_referral_code()
            existing = await self.get_by_referral_code(code)
            if existing is None:
                return code
