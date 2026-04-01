from __future__ import annotations

import asyncio

from aiogram import Bot
from aiogram.exceptions import TelegramAPIError

from app.bot.keyboards.chat import chat_summary_keyboard
from app.bot.keyboards.common import main_menu_keyboard
from app.db.models.session import ChatSession
from app.db.repositories.session_repository import SessionRepository
from app.logging import get_logger
from app.schemas.session import SessionEndResult
from app.services.exceptions import ConflictError, NotFoundError
from app.services.ops_service import OpsService
from app.services.queue_service import QueueService
from app.utils.enums import DeliveryStatus, EndReason, SessionStatus
from app.utils.text import build_chat_summary_text
from app.utils.time import utcnow

END_LOCK_RETRIES = 5
END_LOCK_RETRY_DELAY_SECONDS = 0.05


class SessionService:
    def __init__(
        self,
        bot: Bot,
        session_repository: SessionRepository,
        export_service: "ExportService",
        queue_service: QueueService,
        ops_service: OpsService,
    ) -> None:
        self.bot = bot
        self.session_repository = session_repository
        self.export_service = export_service
        self.queue_service = queue_service
        self.ops_service = ops_service
        self.logger = get_logger(__name__)

    async def get_active_session_for_user(self, user_id: int) -> ChatSession | None:
        return await self.session_repository.get_active_by_user_id(user_id)

    async def get_session_for_user(self, session_id: int, user_id: int) -> ChatSession | None:
        return await self.session_repository.get_with_details_for_user(session_id, user_id)

    async def create_session(self, user1_id: int, user2_id: int) -> ChatSession:
        for user_id in (user1_id, user2_id):
            existing = await self.session_repository.get_active_by_user_id_for_update(user_id)
            if existing is not None:
                raise ConflictError("One of the users is already in an active session.")

        ordered_user_ids = tuple(sorted((user1_id, user2_id)))
        chat_session = await self.session_repository.create(*ordered_user_ids)
        await self.session_repository.session.commit()
        return chat_session

    async def end_session(
        self,
        session_id: int,
        reason: EndReason,
        *,
        ended_by_user_id: int | None = None,
        notify_users: bool = True,
        prelocked_user_ids: set[int] | None = None,
    ) -> SessionEndResult:
        chat_session = await self.session_repository.get_with_details(session_id)
        if chat_session is None:
            raise NotFoundError("Session not found.")

        locked_user_ids = {chat_session.user1_id, chat_session.user2_id}
        if prelocked_user_ids == locked_user_ids:
            chat_session, already_ended = await self._end_locked_session(
                session_id,
                reason,
                ended_by_user_id=ended_by_user_id,
            )
        else:
            chat_session, already_ended = await self._end_with_user_locks(
                session_id,
                reason,
                user_ids=list(locked_user_ids),
                ended_by_user_id=ended_by_user_id,
            )

        if notify_users and not already_ended:
            await self._notify_users(chat_session, reason, ended_by_user_id)

        if not already_ended:
            try:
                await self.export_service.export_session(chat_session.id)
            except Exception as exc:  # pragma: no cover
                self.logger.exception(
                    "session_export_failed",
                    session_id=chat_session.id,
                    error=str(exc),
                )

        return SessionEndResult(
            session_id=chat_session.id,
            status=chat_session.status,
            end_reason=reason,
            ended_at=chat_session.ended_at,
            already_ended=already_ended,
        )

    async def end_active_session_for_user(
        self,
        user_id: int,
        reason: EndReason,
        *,
        ended_by_user_id: int | None = None,
        notify_users: bool = True,
    ) -> SessionEndResult | None:
        active_session = await self.get_active_session_for_user(user_id)
        if active_session is None:
            return None
        return await self.end_session(
            active_session.id,
            reason,
            ended_by_user_id=ended_by_user_id,
            notify_users=notify_users,
        )

    async def _end_with_user_locks(
        self,
        session_id: int,
        reason: EndReason,
        *,
        user_ids: list[int],
        ended_by_user_id: int | None,
    ) -> tuple[ChatSession, bool]:
        for attempt in range(END_LOCK_RETRIES):
            async with self.queue_service.multi_user_lock(user_ids) as locked:
                if locked:
                    return await self._end_locked_session(
                        session_id,
                        reason,
                        ended_by_user_id=ended_by_user_id,
                    )
            if attempt < END_LOCK_RETRIES - 1:
                await asyncio.sleep(END_LOCK_RETRY_DELAY_SECONDS)

        raise ConflictError("Please try again in a moment.")

    async def _end_locked_session(
        self,
        session_id: int,
        reason: EndReason,
        *,
        ended_by_user_id: int | None,
    ) -> tuple[ChatSession, bool]:
        chat_session = await self.session_repository.get_with_details_for_update(session_id)
        if chat_session is None:
            raise NotFoundError("Session not found.")

        if chat_session.status == SessionStatus.ENDED and chat_session.ended_at is not None:
            return chat_session, True

        chat_session.status = SessionStatus.ENDED
        chat_session.end_reason = reason
        chat_session.ended_at = utcnow()
        chat_session.ended_by_user_id = ended_by_user_id

        await self.session_repository.save(chat_session)
        await self.session_repository.session.commit()
        self.logger.info(
            "session_ended",
            session_id=chat_session.id,
            reason=reason.value,
            ended_by_user_id=ended_by_user_id,
        )
        return chat_session, False

    async def _notify_users(
        self,
        chat_session: ChatSession,
        reason: EndReason,
        ended_by_user_id: int | None,
    ) -> None:
        if reason == EndReason.END:
            delivered_count = sum(
                1
                for message in chat_session.messages
                if message.delivery_status == DeliveryStatus.DELIVERED
            )
            summary_text = build_chat_summary_text(
                chat_session.started_at,
                chat_session.ended_at,
                delivered_count,
            )
            for telegram_id in (chat_session.user1.telegram_id, chat_session.user2.telegram_id):
                try:
                    await self.bot.send_message(
                        telegram_id,
                        summary_text,
                        reply_markup=chat_summary_keyboard(chat_session.id),
                    )
                except TelegramAPIError as exc:
                    self.logger.warning(
                        "session_summary_notify_failed",
                        session_id=chat_session.id,
                        telegram_id=telegram_id,
                        error=str(exc),
                    )
            return

        recipients = (
            (chat_session.user1_id, chat_session.user1.telegram_id),
            (chat_session.user2_id, chat_session.user2.telegram_id),
        )

        for user_id, telegram_id in recipients:
            initiated_by_user = ended_by_user_id == user_id
            if reason == EndReason.NEXT and initiated_by_user:
                continue
            if reason == EndReason.REPORT and initiated_by_user:
                continue

            text = self._build_end_copy(initiated_by_user, reason)
            try:
                await self.bot.send_message(
                    telegram_id,
                    text,
                    reply_markup=main_menu_keyboard(),
                )
            except TelegramAPIError as exc:
                self.logger.warning(
                    "session_end_notify_failed",
                    session_id=chat_session.id,
                    telegram_id=telegram_id,
                    error=str(exc),
                )

    def _build_end_copy(self, initiated_by_user: bool, reason: EndReason) -> str:
        if reason == EndReason.NEXT:
            return (
                "\U0001f44b Chat Ended\nFinding your next match..."
                if initiated_by_user
                else "\U0001f44b Chat Ended\nYour match moved on."
            )
        if reason == EndReason.REPORT:
            return (
                "\U0001f44b Chat Ended\nReport saved."
                if initiated_by_user
                else "\U0001f44b Chat Ended"
            )
        if reason == EndReason.PARTNER_UNREACHABLE:
            return "\U0001f44b Chat Ended\nYour match is unavailable."
        if reason == EndReason.MODERATION:
            return "\U0001f44b Chat Ended\nClosed by moderation."
        if reason == EndReason.INTERNAL_FAILURE:
            return "\U0001f44b Chat Ended\nSomething went wrong."
        return "\U0001f44b Chat Ended"
