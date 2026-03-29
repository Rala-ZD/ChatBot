from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.session_message import SessionMessage


class SessionMessageRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(self, message: SessionMessage) -> SessionMessage:
        self.session.add(message)
        await self.session.flush()
        return message

    async def list_for_session(self, session_id: int) -> list[SessionMessage]:
        result = await self.session.execute(
            select(SessionMessage)
            .where(SessionMessage.session_id == session_id)
            .order_by(SessionMessage.created_at.asc(), SessionMessage.id.asc())
        )
        return list(result.scalars().all())

