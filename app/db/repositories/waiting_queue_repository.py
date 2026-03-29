from __future__ import annotations

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.waiting_queue import WaitingQueueEntry
from app.utils.enums import QueueStatus


class WaitingQueueRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_active_by_user_id(self, user_id: int) -> WaitingQueueEntry | None:
        result = await self.session.execute(
            select(WaitingQueueEntry).where(
                WaitingQueueEntry.user_id == user_id,
                WaitingQueueEntry.status == QueueStatus.WAITING,
            )
        )
        return result.scalar_one_or_none()

    async def get_active_by_user_id_for_update(self, user_id: int) -> WaitingQueueEntry | None:
        result = await self.session.execute(
            select(WaitingQueueEntry)
            .where(
                WaitingQueueEntry.user_id == user_id,
                WaitingQueueEntry.status == QueueStatus.WAITING,
            )
            .with_for_update()
        )
        return result.scalar_one_or_none()

    async def add_waiting(self, user_id: int) -> WaitingQueueEntry:
        entry = WaitingQueueEntry(user_id=user_id, status=QueueStatus.WAITING)
        self.session.add(entry)
        await self.session.flush()
        return entry

    async def update_status(self, user_id: int, status: QueueStatus) -> None:
        await self.session.execute(
            update(WaitingQueueEntry)
            .where(
                WaitingQueueEntry.user_id == user_id,
                WaitingQueueEntry.status == QueueStatus.WAITING,
            )
            .values(status=status)
        )

    async def increment_attempts(self, user_id: int) -> None:
        entry = await self.get_active_by_user_id(user_id)
        if entry:
            entry.match_attempts += 1
            await self.session.flush()
