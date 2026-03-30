from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

from aiogram import BaseMiddleware, Bot
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.config import Settings
from app.db.repositories import (
    BanRepository,
    PointPurchaseRepository,
    ReportRepository,
    SessionMessageRepository,
    SessionRepository,
    SessionRatingRepository,
    UserRepository,
    WaitingQueueRepository,
)
from app.services.admin_service import AdminService
from app.services.export_service import ExportService
from app.services.match_service import MatchService
from app.services.moderation_service import ModerationService
from app.services.ops_service import OpsService
from app.services.payment_service import PaymentService
from app.services.queue_service import QueueService
from app.services.rating_service import RatingService
from app.services.relay_service import RelayService
from app.services.session_service import SessionService
from app.services.user_service import UserService


class DbSessionMiddleware(BaseMiddleware):
    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        redis: Redis,
        settings: Settings,
        bot: Bot,
    ) -> None:
        self.session_factory = session_factory
        self.redis = redis
        self.settings = settings
        self.bot = bot

    async def __call__(
        self,
        handler: Callable[[Any, dict[str, Any]], Awaitable[Any]],
        event: Any,
        data: dict[str, Any],
    ) -> Any:
        async with self.session_factory() as session:
            user_repository = UserRepository(session)
            waiting_queue_repository = WaitingQueueRepository(session)
            session_repository = SessionRepository(session)
            session_message_repository = SessionMessageRepository(session)
            session_rating_repository = SessionRatingRepository(session)
            point_purchase_repository = PointPurchaseRepository(session)
            report_repository = ReportRepository(session)
            ban_repository = BanRepository(session)

            queue_service = QueueService(self.redis, self.settings)
            ops_service = OpsService(self.redis, self.settings)
            user_service = UserService(user_repository, self.settings, self.redis)
            payment_service = PaymentService(
                self.settings,
                user_repository,
                point_purchase_repository,
                ops_service,
            )
            export_service = ExportService(
                self.settings,
                self.bot,
                session_repository,
                session_message_repository,
            )
            session_service = SessionService(self.bot, session_repository, export_service, queue_service, ops_service)
            rating_service = RatingService(
                session_repository,
                session_rating_repository,
                user_repository,
            )
            moderation_service = ModerationService(
                self.settings,
                self.bot,
                user_repository,
                ban_repository,
                report_repository,
            )
            match_service = MatchService(
                self.bot,
                user_repository,
                waiting_queue_repository,
                session_repository,
                session_service,
                queue_service,
                ops_service,
                self.settings.match_scan_limit,
            )
            relay_service = RelayService(
                self.bot,
                user_repository,
                session_message_repository,
                session_service,
            )
            admin_service = AdminService(
                user_repository,
                ban_repository,
                session_repository,
                waiting_queue_repository,
            )

            data.update(
                {
                    "db_session": session,
                    "settings": self.settings,
                    "redis": self.redis,
                    "user_repository": user_repository,
                    "waiting_queue_repository": waiting_queue_repository,
                    "session_repository": session_repository,
                    "user_service": user_service,
                    "payment_service": payment_service,
                    "queue_service": queue_service,
                    "ops_service": ops_service,
                    "match_service": match_service,
                    "session_service": session_service,
                    "rating_service": rating_service,
                    "relay_service": relay_service,
                    "moderation_service": moderation_service,
                    "admin_service": admin_service,
                }
            )

            try:
                return await handler(event, data)
            except Exception:
                await session.rollback()
                raise
