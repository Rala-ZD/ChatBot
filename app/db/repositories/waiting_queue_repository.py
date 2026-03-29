from __future__ import annotations

from datetime import datetime

from sqlalchemy import and_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import QueueStatus, User, WaitingQueue


class WaitingQueueRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_active_entry_for_user(self, user_id: int) -> WaitingQueue | None:
        result = await self.session.execute(
            select(WaitingQueue).where(
                WaitingQueue.user_id == user_id,
                WaitingQueue.status == QueueStatus.WAITING,
            )
        )
        return result.scalar_one_or_none()

    async def add_waiting_user(self, user_id: int) -> WaitingQueue:
        entry = WaitingQueue(user_id=user_id, status=QueueStatus.WAITING)
        self.session.add(entry)
        await self.session.flush()
        return entry

    async def get_candidates(self, excluding_user_id: int) -> list[tuple[WaitingQueue, User]]:
        result = await self.session.execute(
            select(WaitingQueue, User)
            .join(User, User.id == WaitingQueue.user_id)
            .where(
                WaitingQueue.status == QueueStatus.WAITING,
                WaitingQueue.user_id != excluding_user_id,
                User.is_registered.is_(True),
                User.is_banned.is_(False),
                User.is_in_chat.is_(False),
            )
            .order_by(WaitingQueue.joined_at.asc(), WaitingQueue.id.asc())
        )
        return list(result.all())

    async def mark_users_as(
        self,
        user_ids: list[int],
        status: QueueStatus,
        *,
        before: datetime | None = None,
    ) -> None:
        conditions = [
            WaitingQueue.user_id.in_(user_ids),
            WaitingQueue.status == QueueStatus.WAITING,
        ]
        if before is not None:
            conditions.append(WaitingQueue.joined_at <= before)
        await self.session.execute(
            update(WaitingQueue)
            .where(and_(*conditions))
            .values(status=status)
        )

    async def cancel_all_waiting_for_user(self, user_id: int) -> None:
        await self.mark_users_as([user_id], QueueStatus.CANCELLED)
