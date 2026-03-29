from __future__ import annotations

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.models.session import ChatSession
from app.utils.enums import SessionStatus


class SessionRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_by_id(self, session_id: int) -> ChatSession | None:
        return await self.session.get(ChatSession, session_id)

    async def get_with_details(self, session_id: int) -> ChatSession | None:
        result = await self.session.execute(
            select(ChatSession)
            .options(
                selectinload(ChatSession.user1),
                selectinload(ChatSession.user2),
                selectinload(ChatSession.messages),
                selectinload(ChatSession.reports),
            )
            .where(ChatSession.id == session_id)
        )
        return result.scalar_one_or_none()

    async def get_with_details_for_update(self, session_id: int) -> ChatSession | None:
        result = await self.session.execute(
            select(ChatSession)
            .options(
                selectinload(ChatSession.user1),
                selectinload(ChatSession.user2),
                selectinload(ChatSession.messages),
                selectinload(ChatSession.reports),
            )
            .where(ChatSession.id == session_id)
            .with_for_update()
        )
        return result.scalar_one_or_none()

    async def get_active_by_user_id(self, user_id: int) -> ChatSession | None:
        result = await self.session.execute(
            select(ChatSession)
            .options(selectinload(ChatSession.user1), selectinload(ChatSession.user2))
            .where(
                or_(ChatSession.user1_id == user_id, ChatSession.user2_id == user_id),
                ChatSession.status == SessionStatus.ACTIVE,
            )
        )
        return result.scalar_one_or_none()

    async def get_active_by_user_id_for_update(self, user_id: int) -> ChatSession | None:
        result = await self.session.execute(
            select(ChatSession)
            .options(selectinload(ChatSession.user1), selectinload(ChatSession.user2))
            .where(
                or_(ChatSession.user1_id == user_id, ChatSession.user2_id == user_id),
                ChatSession.status == SessionStatus.ACTIVE,
            )
            .with_for_update()
        )
        return result.scalar_one_or_none()

    async def create(self, user1_id: int, user2_id: int) -> ChatSession:
        session = ChatSession(user1_id=user1_id, user2_id=user2_id)
        self.session.add(session)
        await self.session.flush()
        return session

    async def save(self, chat_session: ChatSession) -> ChatSession:
        self.session.add(chat_session)
        await self.session.flush()
        return chat_session
