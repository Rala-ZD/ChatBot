from __future__ import annotations

from aiogram import Bot

from app.config import Settings
from app.db.models.ban import Ban
from app.db.models.report import Report
from app.db.models.session import ChatSession
from app.db.models.user import User
from app.db.repositories.ban_repository import BanRepository
from app.db.repositories.report_repository import ReportRepository
from app.db.repositories.user_repository import UserRepository
from app.schemas.moderation import BanCreate, ReportCreate
from app.services.exceptions import AccessDeniedError, NotFoundError
from app.utils.time import utcnow


class ModerationService:
    def __init__(
        self,
        settings: Settings,
        bot: Bot,
        user_repository: UserRepository,
        ban_repository: BanRepository,
        report_repository: ReportRepository,
    ) -> None:
        self.settings = settings
        self.bot = bot
        self.user_repository = user_repository
        self.ban_repository = ban_repository
        self.report_repository = report_repository

    def ensure_not_banned(self, user: User) -> None:
        if user.is_banned:
            raise AccessDeniedError("Your access to this bot is currently restricted.")

    async def create_report(
        self,
        chat_session: ChatSession,
        reporter: User,
        reason: str,
    ) -> Report:
        if reporter.id not in {chat_session.user1_id, chat_session.user2_id}:
            raise AccessDeniedError("You can only report your own chats.")
        partner_id = chat_session.partner_id_for(reporter.id)
        payload = ReportCreate(
            session_id=chat_session.id,
            reporter_user_id=reporter.id,
            reported_user_id=partner_id,
            reason=reason.strip(),
        )
        report = Report(**payload.model_dump(), reason_code=None)
        await self.report_repository.create(report)
        await self.report_repository.session.commit()

        await self.bot.send_message(
            self.settings.admin_channel_id,
            (
                f"New report in session #{chat_session.id}\n"
                f"Reporter: internal_id={reporter.id}, telegram_id={reporter.telegram_id}\n"
                f"Reported: internal_id={partner_id}\n"
                f"Reason: {payload.reason}"
            ),
        )
        return report

    async def ban_user(self, payload: BanCreate) -> Ban:
        user = await self.user_repository.get_by_id(payload.user_id)
        if user is None:
            raise NotFoundError("User not found.")

        existing = await self.ban_repository.get_active_by_user_id(payload.user_id)
        if existing is not None:
            return existing

        user.is_banned = True
        ban = Ban(
            user_id=payload.user_id,
            reason=payload.reason,
            banned_by=payload.banned_by,
        )
        await self.ban_repository.create(ban)
        await self.user_repository.save(user)
        await self.ban_repository.session.commit()
        return ban

    async def unban_user(self, user_id: int, revoked_by: int) -> Ban:
        active_ban = await self.ban_repository.get_active_by_user_id(user_id)
        if active_ban is None:
            raise NotFoundError("No active ban found for that user.")

        user = await self.user_repository.get_by_id(user_id)
        if user is None:
            raise NotFoundError("User not found.")

        active_ban.is_active = False
        active_ban.revoked_at = utcnow()
        active_ban.revoked_by = revoked_by
        user.is_banned = False

        await self.ban_repository.save(active_ban)
        await self.user_repository.save(user)
        await self.ban_repository.session.commit()
        return active_ban
