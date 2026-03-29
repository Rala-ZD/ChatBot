from __future__ import annotations

from aiogram import Bot
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.config import Settings
from app.services.admin_service import AdminService
from app.services.export_service import ExportService
from app.services.match_service import MatchService
from app.services.moderation_service import ModerationService
from app.services.relay_service import RelayService
from app.services.session_service import SessionService
from app.services.user_service import UserService
from app.utils.redis import RedisRateLimiter


class ServiceContainer:
    def __init__(
        self,
        session_factory: async_sessionmaker,
        redis: Redis,
        bot: Bot,
        settings: Settings,
    ) -> None:
        self.settings = settings
        self.session_factory = session_factory
        self.redis = redis
        self.bot = bot

        self.user_service = UserService(session_factory, settings)
        self.export_service = ExportService(session_factory, redis, bot, settings)
        self.session_service = SessionService(session_factory, redis, bot, settings)
        self.session_service.bind_export_service(self.export_service)
        self.match_service = MatchService(session_factory, redis, bot, settings)
        self.relay_service = RelayService(
            session_factory,
            redis,
            bot,
            settings,
            self.session_service,
        )
        self.moderation_service = ModerationService(
            session_factory,
            redis,
            bot,
            settings,
            self.session_service,
            self.match_service,
        )
        self.admin_service = AdminService(session_factory, self.export_service)
        self.rate_limiter = RedisRateLimiter(redis, settings.rate_limit_window_seconds)
