from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import User


class UserRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_by_telegram_id(self, telegram_id: int) -> User | None:
        result = await self.session.execute(
            select(User).where(User.telegram_id == telegram_id)
        )
        return result.scalar_one_or_none()

    async def get_by_id(self, user_id: int) -> User | None:
        result = await self.session.execute(select(User).where(User.id == user_id))
        return result.scalar_one_or_none()

    async def list_by_ids(self, user_ids: list[int]) -> list[User]:
        result = await self.session.execute(select(User).where(User.id.in_(user_ids)))
        return list(result.scalars().all())

    async def get_or_create_by_telegram_identity(
        self,
        telegram_id: int,
        username: str | None,
        first_name: str | None,
    ) -> User:
        user = await self.get_by_telegram_id(telegram_id)
        if user is None:
            user = User(
                telegram_id=telegram_id,
                username=username,
                first_name=first_name,
                interests_json=[],
            )
            self.session.add(user)
            await self.session.flush()
            return user

        user.username = username
        user.first_name = first_name
        await self.session.flush()
        return user
