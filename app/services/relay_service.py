from __future__ import annotations

from aiogram import Bot
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError
from aiogram.types import Message
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.config import Settings
from app.db.models import MessageType, SessionEndReason
from app.db.repositories.session_message_repository import SessionMessageRepository
from app.db.session import session_scope
from app.schemas.domain import RelayPayload
from app.services.session_service import SessionService
from app.utils.redis import redis_lock
from app.utils.redis_keys import relay_lock_key


class RelayService:
    def __init__(
        self,
        session_factory: async_sessionmaker,
        redis: Redis,
        bot: Bot,
        settings: Settings,
        session_service: SessionService,
    ) -> None:
        self.session_factory = session_factory
        self.redis = redis
        self.bot = bot
        self.settings = settings
        self.session_service = session_service

    async def relay_message(self, message: Message) -> bool:
        context = await self.session_service.get_active_context_by_telegram_id(message.from_user.id)
        if context is None:
            return False

        payload = self._extract_payload(message)
        if payload is None:
            await message.answer("That content type is not supported in anonymous chat yet.")
            return True

        async with redis_lock(
            self.redis,
            relay_lock_key(str(context.session.id)),
            timeout=self.settings.session_relay_lock_seconds,
            blocking_timeout=self.settings.session_relay_lock_seconds,
        ):
            try:
                copied_message = await self.bot.copy_message(
                    chat_id=context.partner.telegram_id,
                    from_chat_id=message.chat.id,
                    message_id=message.message_id,
                )
            except TelegramForbiddenError:
                await self.session_service.end_session(
                    context.session.id,
                    reason=SessionEndReason.BLOCKED_BOT,
                    actor_user_id=None,
                )
                return True
            except TelegramBadRequest:
                await self.session_service.end_session(
                    context.session.id,
                    reason=SessionEndReason.PARTNER_UNAVAILABLE,
                    actor_user_id=None,
                )
                return True

            async with session_scope(self.session_factory) as session:
                repo = SessionMessageRepository(session)
                await repo.create(
                    session_id=context.session.id,
                    sender_user_id=context.user.id,
                    message_type=payload.message_type,
                    telegram_message_id=copied_message.message_id,
                    text_content=payload.text_content,
                    caption=payload.caption,
                    file_id=payload.file_id,
                    file_unique_id=payload.file_unique_id,
                )
            return True

    def _extract_payload(self, message: Message) -> RelayPayload | None:
        if message.text:
            return RelayPayload(
                message_type=MessageType.TEXT.value,
                text_content=message.text,
                caption=None,
                file_id=None,
                file_unique_id=None,
            )
        if message.photo:
            photo = message.photo[-1]
            return RelayPayload(
                message_type=MessageType.PHOTO.value,
                text_content=None,
                caption=message.caption,
                file_id=photo.file_id,
                file_unique_id=photo.file_unique_id,
            )
        if message.video:
            return RelayPayload(
                message_type=MessageType.VIDEO.value,
                text_content=None,
                caption=message.caption,
                file_id=message.video.file_id,
                file_unique_id=message.video.file_unique_id,
            )
        if message.voice:
            return RelayPayload(
                message_type=MessageType.VOICE.value,
                text_content=None,
                caption=message.caption,
                file_id=message.voice.file_id,
                file_unique_id=message.voice.file_unique_id,
            )
        if message.document:
            return RelayPayload(
                message_type=MessageType.DOCUMENT.value,
                text_content=None,
                caption=message.caption,
                file_id=message.document.file_id,
                file_unique_id=message.document.file_unique_id,
            )
        if message.sticker:
            return RelayPayload(
                message_type=MessageType.STICKER.value,
                text_content=None,
                caption=None,
                file_id=message.sticker.file_id,
                file_unique_id=message.sticker.file_unique_id,
            )
        return None
