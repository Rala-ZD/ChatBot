from __future__ import annotations

from datetime import UTC, datetime

from aiogram import Bot
from aiogram.exceptions import TelegramAPIError
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.config import Settings
from app.db.models import ReportReason, SessionEndReason
from app.db.repositories.ban_repository import BanRepository
from app.db.repositories.report_repository import ReportRepository
from app.db.repositories.session_repository import SessionRepository
from app.db.repositories.user_repository import UserRepository
from app.db.repositories.waiting_queue_repository import WaitingQueueRepository
from app.db.session import session_scope
from app.services.match_service import MatchService
from app.services.session_service import SessionService
from app.utils.exceptions import ConflictError, UserVisibleError


class ModerationService:
    def __init__(
        self,
        session_factory: async_sessionmaker,
        redis: Redis,
        bot: Bot,
        settings: Settings,
        session_service: SessionService,
        match_service: MatchService,
    ) -> None:
        self.session_factory = session_factory
        self.redis = redis
        self.bot = bot
        self.settings = settings
        self.session_service = session_service
        self.match_service = match_service

    async def submit_report(
        self,
        reporter_telegram_id: int,
        *,
        reason: ReportReason,
        note: str | None = None,
    ) -> int:
        context = await self.session_service.get_active_context_by_telegram_id(reporter_telegram_id)
        if context is None:
            raise UserVisibleError("You can only report a user during an active chat.")

        cleaned_note = note.strip() if note else None
        if cleaned_note and len(cleaned_note) > self.settings.max_report_note_length:
            raise UserVisibleError(
                f"Report note must be {self.settings.max_report_note_length} characters or fewer."
            )

        async with session_scope(self.session_factory) as session:
            repo = ReportRepository(session)
            report = await repo.create(
                session_id=context.session.id,
                reporter_user_id=context.user.id,
                reported_user_id=context.partner.id,
                reason=reason.value,
                note=cleaned_note,
            )
            report_id = report.id

        await self.bot.send_message(
            chat_id=self.settings.admin_channel_id,
            text=(
                "<b>New user report</b>\n"
                f"Report ID: {report_id}\n"
                f"Session ID: <code>{context.session.id}</code>\n"
                f"Reporter internal ID: {context.user.id}\n"
                f"Reported internal ID: {context.partner.id}\n"
                f"Reason: {reason.value}\n"
                f"Note: {cleaned_note or '-'}"
            ),
        )
        await self.session_service.end_session(
            context.session.id,
            reason=SessionEndReason.REPORT,
            actor_user_id=context.user.id,
        )
        return report_id

    async def ban_user(self, *, user_id: int, reason: str, banned_by: int) -> None:
        cleaned_reason = reason.strip()
        if not cleaned_reason:
            raise UserVisibleError("Ban reason is required.")

        active_session_id = None
        telegram_id = None
        async with session_scope(self.session_factory) as session:
            user_repo = UserRepository(session)
            ban_repo = BanRepository(session)
            session_repo = SessionRepository(session)
            queue_repo = WaitingQueueRepository(session)

            user = await user_repo.get_by_id(user_id)
            if user is None:
                raise UserVisibleError("User not found.")
            if await ban_repo.get_active_by_user_id(user_id):
                raise ConflictError("This user is already banned.")

            active_session = await session_repo.get_active_by_user_id(user_id)
            active_session_id = active_session.id if active_session else None
            telegram_id = user.telegram_id

            await ban_repo.create(user_id=user_id, reason=cleaned_reason, banned_by=banned_by)
            user.is_banned = True
            await queue_repo.cancel_all_waiting_for_user(user_id)

        await self.match_service.cancel_waiting_by_user_id(user_id)
        if active_session_id is not None:
            await self.session_service.end_session(
                active_session_id,
                reason=SessionEndReason.MODERATION,
                actor_user_id=None,
            )
        if telegram_id is not None:
            try:
                await self.bot.send_message(
                    chat_id=telegram_id,
                    text="Your access to this bot has been restricted by moderation.",
                )
            except TelegramAPIError:
                pass

    async def unban_user(self, *, user_id: int, revoked_by: int) -> None:
        async with session_scope(self.session_factory) as session:
            user_repo = UserRepository(session)
            ban_repo = BanRepository(session)

            user = await user_repo.get_by_id(user_id)
            if user is None:
                raise UserVisibleError("User not found.")
            revoked = await ban_repo.revoke_active(
                user_id=user_id,
                revoked_by=revoked_by,
                revoked_at=datetime.now(UTC),
            )
            if not revoked:
                raise ConflictError("This user is not currently banned.")
            user.is_banned = False

    async def list_recent_reports(self, limit: int = 50):
        async with session_scope(self.session_factory) as session:
            repo = ReportRepository(session)
            return await repo.list_recent(limit=limit)
