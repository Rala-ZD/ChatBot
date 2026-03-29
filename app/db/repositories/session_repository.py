from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Session, SessionStatus


class SessionRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_by_id(self, session_id: uuid.UUID) -> Session | None:
        result = await self.session.execute(select(Session).where(Session.id == session_id))
        return result.scalar_one_or_none()

    async def get_active_by_user_id(self, user_id: int) -> Session | None:
        result = await self.session.execute(
            select(Session).where(
                Session.status == SessionStatus.ACTIVE,
                or_(Session.user1_id == user_id, Session.user2_id == user_id),
            )
        )
        return result.scalar_one_or_none()

    async def create_session(self, user1_id: int, user2_id: int) -> Session:
        session = Session(user1_id=user1_id, user2_id=user2_id, status=SessionStatus.ACTIVE)
        self.session.add(session)
        await self.session.flush()
        return session

    async def end_session(
        self,
        session_id: uuid.UUID,
        *,
        ended_at: datetime,
        end_reason: str,
    ) -> int:
        result = await self.session.execute(
            update(Session)
            .where(Session.id == session_id, Session.status == SessionStatus.ACTIVE)
            .values(
                status=SessionStatus.ENDED,
                ended_at=ended_at,
                end_reason=end_reason,
            )
        )
        return result.rowcount or 0

    async def mark_exported(self, session_id: uuid.UUID, exported_at: datetime) -> None:
        await self.session.execute(
            update(Session)
            .where(Session.id == session_id, Session.exported_at.is_(None))
            .values(exported_at=exported_at)
        )
