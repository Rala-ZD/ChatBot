from __future__ import annotations

from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.base import DefaultKeyBuilder
from aiogram.fsm.storage.redis import RedisStorage
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.bot.handlers.admin import router as admin_router
from app.bot.handlers.chat import router as chat_router
from app.bot.handlers.matchmaking import router as matchmaking_router
from app.bot.handlers.menu import router as menu_router
from app.bot.handlers.moderation import router as moderation_router
from app.bot.handlers.payments import router as payments_router
from app.bot.handlers.profile import router as profile_router
from app.bot.handlers.ratings import router as ratings_router
from app.bot.handlers.referral import router as referral_router
from app.bot.handlers.registration import router as registration_router
from app.bot.handlers.select_gender import router as select_gender_router
from app.bot.handlers.start import router as start_router
from app.bot.middlewares.access import AccessMiddleware
from app.bot.middlewares.db import DbSessionMiddleware
from app.bot.middlewares.error_handler import ErrorHandlerMiddleware
from app.bot.middlewares.throttling import ThrottlingMiddleware
from app.config import Settings
from app.services.ops_service import OpsService


def create_dispatcher(
    settings: Settings,
    session_factory: async_sessionmaker[AsyncSession],
    redis: Redis,
    bot: Bot,
) -> Dispatcher:
    dispatcher = Dispatcher(
        storage=RedisStorage(
            redis,
            key_builder=DefaultKeyBuilder(with_bot_id=True, with_destiny=True),
        )
    )
    ops_service = OpsService(redis, settings)

    dispatcher.update.outer_middleware(ErrorHandlerMiddleware(ops_service))
    dispatcher.update.outer_middleware(DbSessionMiddleware(session_factory, redis, settings, bot))
    dispatcher.update.outer_middleware(AccessMiddleware())
    dispatcher.message.outer_middleware(ThrottlingMiddleware(redis, settings))
    dispatcher.callback_query.outer_middleware(ThrottlingMiddleware(redis, settings))

    dispatcher.include_router(start_router)
    dispatcher.include_router(registration_router)
    dispatcher.include_router(profile_router)
    dispatcher.include_router(referral_router)
    dispatcher.include_router(payments_router)
    dispatcher.include_router(select_gender_router)
    dispatcher.include_router(matchmaking_router)
    dispatcher.include_router(moderation_router)
    dispatcher.include_router(ratings_router)
    dispatcher.include_router(chat_router)
    dispatcher.include_router(menu_router)
    dispatcher.include_router(admin_router)
    dispatcher.workflow_data.update({"settings": settings})

    return dispatcher
