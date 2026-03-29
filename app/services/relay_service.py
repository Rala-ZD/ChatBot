from __future__ import annotations

from aiogram import Bot
from aiogram.exceptions import TelegramAPIError, TelegramBadRequest, TelegramForbiddenError
from aiogram.types import Message

from app.db.models.session import ChatSession
from app.db.models.session_message import SessionMessage
from app.db.models.user import User
from app.db.repositories.session_message_repository import SessionMessageRepository
from app.db.repositories.user_repository import UserRepository
from app.logging import get_logger
from app.services.exceptions import ConflictError
from app.services.session_service import SessionService
from app.utils.enums import DeliveryStatus, EndReason
from app.utils.telegram import (
    extract_file_metadata,
    is_early_chat_restricted,
    message_has_restricted_content,
    resolve_message_type,
    supported_for_relay,
)
from app.utils.text import EARLY_CHAT_RESTRICTION_TEXT


class RelayService:
    def __init__(
        self,
        bot: Bot,
        user_repository: UserRepository,
        session_message_repository: SessionMessageRepository,
        session_service: SessionService,
    ) -> None:
        self.bot = bot
        self.user_repository = user_repository
        self.session_message_repository = session_message_repository
        self.session_service = session_service
        self.logger = get_logger(__name__)

    async def relay_message(self, sender: User, message: Message) -> None:
        chat_session = await self.session_service.get_active_session_for_user(sender.id)
        if chat_session is None:
            raise ConflictError("You are not in an active chat.")

        partner = await self.user_repository.get_by_id(chat_session.partner_id_for(sender.id))
        if partner is None:
            await self.session_service.end_session(
                chat_session.id,
                EndReason.INTERNAL_FAILURE,
                ended_by_user_id=sender.id,
            )
            raise ConflictError("The chat could not continue.")

        message_type = resolve_message_type(message)
        file_id, file_unique_id = extract_file_metadata(message)
        record = SessionMessage(
            session_id=chat_session.id,
            sender_user_id=sender.id,
            sender_chat_id=message.chat.id,
            source_message_id=message.message_id,
            telegram_message_id=message.message_id,
            message_type=message_type,
            text_content=message.text,
            caption=message.caption,
            file_id=file_id,
            file_unique_id=file_unique_id,
            metadata_json={},
        )

        restriction_reason = self._early_restriction_reason(chat_session, sender, message)
        if restriction_reason is not None:
            record.delivery_status = DeliveryStatus.FAILED
            record.error_text = f"early_chat_restriction:{restriction_reason}"
            record.metadata_json = {
                "blocked_by": "early_chat_restriction",
                "reason": restriction_reason,
            }
            await self.session_message_repository.create(record)
            await self.session_message_repository.session.commit()
            await self._delete_blocked_message(message)
            await message.answer(EARLY_CHAT_RESTRICTION_TEXT)
            return

        if not supported_for_relay(message):
            record.delivery_status = DeliveryStatus.FAILED
            record.error_text = "unsupported_content_type"
            await self.session_message_repository.create(record)
            await self.session_message_repository.session.commit()
            await message.answer(
                "That content type is not supported yet. Please send text, photos, videos, voice notes, documents, or stickers."
            )
            return

        try:
            copied = await self.bot.copy_message(
                chat_id=partner.telegram_id,
                from_chat_id=message.chat.id,
                message_id=message.message_id,
            )
            record.relay_chat_id = partner.telegram_id
            record.relay_message_id = copied.message_id
            record.delivery_status = DeliveryStatus.DELIVERED
        except (TelegramForbiddenError, TelegramBadRequest) as exc:
            record.delivery_status = DeliveryStatus.FAILED
            record.error_text = str(exc)
            await self.session_message_repository.create(record)
            await self.session_message_repository.session.commit()
            await self.session_service.end_session(
                chat_session.id,
                EndReason.PARTNER_UNREACHABLE,
                ended_by_user_id=sender.id,
            )
            await message.answer("The other user is no longer available. The chat has ended.")
            return
        except TelegramAPIError as exc:
            record.delivery_status = DeliveryStatus.FAILED
            record.error_text = str(exc)
            await self.session_message_repository.create(record)
            await self.session_message_repository.session.commit()
            self.logger.warning(
                "relay_failed",
                session_id=chat_session.id,
                sender_user_id=sender.id,
                error=str(exc),
            )
            await message.answer("That message could not be delivered. Please try again.")
            return

        await self.session_message_repository.create(record)
        await self.session_message_repository.session.commit()

    def _early_restriction_reason(
        self,
        chat_session: ChatSession,
        sender: User,
        message: Message,
    ) -> str | None:
        if not is_early_chat_restricted(chat_session, sender):
            return None
        return message_has_restricted_content(message)

    async def _delete_blocked_message(self, message: Message) -> None:
        try:
            await self.bot.delete_message(
                chat_id=message.chat.id,
                message_id=message.message_id,
            )
        except TelegramAPIError as exc:
            self.logger.warning(
                "blocked_message_delete_failed",
                chat_id=message.chat.id,
                message_id=message.message_id,
                error=str(exc),
            )
