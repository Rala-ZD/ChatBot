from __future__ import annotations

import uuid
from datetime import UTC, datetime

from aiogram import Bot
from aiogram.exceptions import TelegramAPIError
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.config import Settings
from app.db.models import SessionEndReason, SessionStatus
from app.db.repositories.session_repository import SessionRepository
from app.db.repositories.user_repository import UserRepository
from app.db.session import session_scope
from app.schemas.domain import ActiveSessionContext, SessionEndResult
from app.utils.redis import redis_lock
from app.utils.redis_keys import session_end_lock_key


class SessionService:
    def __init__(
        self,
        session_factory: async_sessionmaker,
        redis: Redis,
        bot: Bot,
        settings: Settings,
    ) -> None:
        self.session_factory = session_factory
        self.redis = redis
        self.bot = bot
        self.settings = settings
        self.export_service = None

    def bind_export_service(self, export_service: object) -> None:
        self.export_service = export_service

    async def get_active_context_by_telegram_id(self, telegram_id: int) -> ActiveSessionContext | None:
        async with session_scope(self.session_factory) as session:
            user_repo = UserRepository(session)
            session_repo = SessionRepository(session)
            user = await user_repo.get_by_telegram_id(telegram_id)
            if user is None:
                return None
            active_session = await session_repo.get_active_by_user_id(user.id)
            if active_session is None:
                return None
            partner_id = active_session.user2_id if active_session.user1_id == user.id else active_session.user1_id
            partner = await user_repo.get_by_id(partner_id)
            if partner is None:
                return None
            return ActiveSessionContext(session=active_session, user=user, partner=partner)

    async def get_active_context_by_user_id(self, user_id: int) -> ActiveSessionContext | None:
        async with session_scope(self.session_factory) as session:
            user_repo = UserRepository(session)
            session_repo = SessionRepository(session)
            user = await user_repo.get_by_id(user_id)
            if user is None:
                return None
            active_session = await session_repo.get_active_by_user_id(user.id)
            if active_session is None:
                return None
            partner_id = active_session.user2_id if active_session.user1_id == user.id else active_session.user1_id
            partner = await user_repo.get_by_id(partner_id)
            if partner is None:
                return None
            return ActiveSessionContext(session=active_session, user=user, partner=partner)

    async def end_active_session_by_telegram_id(
        self,
        telegram_id: int,
        reason: SessionEndReason,
    ) -> SessionEndResult:
        context = await self.get_active_context_by_telegram_id(telegram_id)
        if context is None:
            return SessionEndResult(ended=False, session_id=None)
        return await self.end_session(
            context.session.id,
            reason=reason,
            actor_user_id=context.user.id,
        )

    async def end_session(
        self,
        session_id: uuid.UUID,
        *,
        reason: SessionEndReason,
        actor_user_id: int | None = None,
    ) -> SessionEndResult:
        async with redis_lock(
            self.redis,
            session_end_lock_key(str(session_id)),
            timeout=self.settings.match_lock_seconds,
            blocking_timeout=self.settings.match_lock_seconds,
        ):
            async with session_scope(self.session_factory) as session:
                session_repo = SessionRepository(session)
                user_repo = UserRepository(session)

                chat_session = await session_repo.get_by_id(session_id)
                if chat_session is None:
                    return SessionEndResult(ended=False, session_id=None)
                if chat_session.status != SessionStatus.ACTIVE:
                    return SessionEndResult(ended=False, session_id=chat_session.id)

                user1 = await user_repo.get_by_id(chat_session.user1_id)
                user2 = await user_repo.get_by_id(chat_session.user2_id)
                if user1 is None or user2 is None:
                    return SessionEndResult(ended=False, session_id=chat_session.id)

                ended = await session_repo.end_session(
                    chat_session.id,
                    ended_at=datetime.now(UTC),
                    end_reason=reason.value,
                )
                if not ended:
                    return SessionEndResult(ended=False, session_id=chat_session.id)

                user1.is_in_chat = False
                user2.is_in_chat = False

                partner_user_id = None
                if actor_user_id is not None:
                    partner_user_id = user2.id if user1.id == actor_user_id else user1.id
                notifications = self._build_notifications(reason, actor_user_id, user1.id, user2.id)
                user1_telegram_id = user1.telegram_id
                user2_telegram_id = user2.telegram_id

            await self._send_notification(user1_telegram_id, notifications.get(user1.id))
            await self._send_notification(user2_telegram_id, notifications.get(user2.id))
            if self.export_service is not None:
                await self.export_service.export_session(session_id)  # type: ignore[attr-defined]
            return SessionEndResult(
                ended=True,
                session_id=session_id,
                partner_user_id=partner_user_id,
            )

    def _build_notifications(
        self,
        reason: SessionEndReason,
        actor_user_id: int | None,
        user1_id: int,
        user2_id: int,
    ) -> dict[int, str]:
        if reason == SessionEndReason.USER_END:
            return self._actor_partner_map(
                actor_user_id,
                user1_id,
                user2_id,
                actor_text="Chat ended. You are back at the main menu.",
                partner_text="Your stranger ended the chat.",
            )
        if reason == SessionEndReason.NEXT:
            return self._actor_partner_map(
                actor_user_id,
                user1_id,
                user2_id,
                actor_text="Searching for a new stranger...",
                partner_text="Your stranger moved to the next chat.",
            )
        if reason == SessionEndReason.REPORT:
            return self._actor_partner_map(
                actor_user_id,
                user1_id,
                user2_id,
                actor_text="Report submitted. The chat has been closed.",
                partner_text="The chat has been closed.",
            )
        if reason == SessionEndReason.MODERATION:
            return {
                user1_id: "This chat was closed by moderation.",
                user2_id: "This chat was closed by moderation.",
            }
        if reason in {SessionEndReason.PARTNER_UNAVAILABLE, SessionEndReason.BLOCKED_BOT}:
            return {
                user1_id: "The chat ended because one side became unavailable.",
                user2_id: "The chat ended because one side became unavailable.",
            }
        return {
            user1_id: "The chat ended because of an internal issue.",
            user2_id: "The chat ended because of an internal issue.",
        }

    def _actor_partner_map(
        self,
        actor_user_id: int | None,
        user1_id: int,
        user2_id: int,
        *,
        actor_text: str,
        partner_text: str,
    ) -> dict[int, str]:
        if actor_user_id == user1_id:
            return {user1_id: actor_text, user2_id: partner_text}
        if actor_user_id == user2_id:
            return {user1_id: partner_text, user2_id: actor_text}
        return {user1_id: partner_text, user2_id: partner_text}

    async def _send_notification(self, telegram_id: int, text: str | None) -> None:
        if not text:
            return
        try:
            await self.bot.send_message(chat_id=telegram_id, text=text)
        except TelegramAPIError:
            return
