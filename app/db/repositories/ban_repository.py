from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.ban import Ban


class BanRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_active_by_user_id(self, user_id: int) -> Ban | None:
        result = await self.session.execute(
            select(Ban).where(Ban.user_id == user_id, Ban.is_active.is_(True))
        )
        return result.scalar_one_or_none()

    async def create(self, ban: Ban) -> Ban:
        self.session.add(ban)
        await self.session.flush()
        return ban

    async def save(self, ban: Ban) -> Ban:
        self.session.add(ban)
        await self.session.flush()
        return ban
