from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import SessionMessage


class SessionMessageRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(
        self,
        *,
        session_id: uuid.UUID,
        sender_user_id: int,
        message_type: str,
        telegram_message_id: int,
        text_content: str | None,
        caption: str | None,
        file_id: str | None,
        file_unique_id: str | None,
    ) -> SessionMessage:
        entry = SessionMessage(
            session_id=session_id,
            sender_user_id=sender_user_id,
            message_type=message_type,
            telegram_message_id=telegram_message_id,
            text_content=text_content,
            caption=caption,
            file_id=file_id,
            file_unique_id=file_unique_id,
        )
        self.session.add(entry)
        await self.session.flush()
        return entry

    async def list_for_session(self, session_id: uuid.UUID) -> list[SessionMessage]:
        result = await self.session.execute(
            select(SessionMessage)
            .where(SessionMessage.session_id == session_id)
            .order_by(SessionMessage.created_at.asc(), SessionMessage.id.asc())
        )
        return list(result.scalars().all())
