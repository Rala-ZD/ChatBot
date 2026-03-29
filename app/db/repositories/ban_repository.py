from __future__ import annotations

from datetime import datetime

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Ban


class BanRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_active_by_user_id(self, user_id: int) -> Ban | None:
        result = await self.session.execute(
            select(Ban).where(Ban.user_id == user_id, Ban.is_active.is_(True))
        )
        return result.scalar_one_or_none()

    async def create(self, *, user_id: int, reason: str, banned_by: int) -> Ban:
        ban = Ban(user_id=user_id, reason=reason, banned_by=banned_by, is_active=True)
        self.session.add(ban)
        await self.session.flush()
        return ban

    async def revoke_active(
        self,
        *,
        user_id: int,
        revoked_by: int,
        revoked_at: datetime,
    ) -> int:
        result = await self.session.execute(
            update(Ban)
            .where(Ban.user_id == user_id, Ban.is_active.is_(True))
            .values(is_active=False, revoked_at=revoked_at, revoked_by=revoked_by)
        )
        return result.rowcount or 0
