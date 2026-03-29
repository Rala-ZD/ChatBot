from __future__ import annotations

from contextlib import asynccontextmanager

from aiogram import Bot
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.types import BotCommand
from fastapi import FastAPI
from redis.asyncio import Redis

from app.api.routes import admin, health, webhook
from app.bot.setup import create_dispatcher
from app.config import get_settings, settings_as_log_context
from app.db.session import create_engine_from_settings, create_session_factory
from app.logging import configure_logging, get_logger
from app.services.container import ServiceContainer


async def set_bot_commands(bot: Bot) -> None:
    await bot.set_my_commands(
        [
            BotCommand(command="start", description="Start the bot"),
            BotCommand(command="help", description="Show help"),
            BotCommand(command="rules", description="Show rules"),
            BotCommand(command="profile", description="View your profile"),
            BotCommand(command="cancel", description="Cancel current step or search"),
            BotCommand(command="next", description="Skip to the next stranger"),
            BotCommand(command="end", description="End the current chat"),
            BotCommand(command="report", description="Report the current stranger"),
        ]
    )


def create_app() -> FastAPI:
    settings = get_settings()
    configure_logging(settings.log_level)
    logger = get_logger(__name__).bind(**settings_as_log_context(settings))

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        engine = create_engine_from_settings(settings)
        session_factory = create_session_factory(engine)
        redis = Redis.from_url(settings.redis_dsn, encoding="utf-8", decode_responses=True)
        bot = Bot(
            token=settings.bot_token.get_secret_value(),
            default=DefaultBotProperties(parse_mode=ParseMode.HTML),
        )
        services = ServiceContainer(session_factory, redis, bot, settings)
        dispatcher = create_dispatcher(services)

        app.state.settings = settings
        app.state.engine = engine
        app.state.redis = redis
        app.state.bot = bot
        app.state.services = services
        app.state.dispatcher = dispatcher

        await redis.ping()
        await set_bot_commands(bot)
        await bot.set_webhook(
            url=settings.webhook_url,
            secret_token=settings.webhook_secret.get_secret_value(),
            allowed_updates=dispatcher.resolve_used_update_types(),
            drop_pending_updates=settings.webhook_drop_pending_updates,
        )
        logger.info("application_started")
        try:
            yield
        finally:
            await bot.delete_webhook(drop_pending_updates=False)
            await bot.session.close()
            await redis.aclose()
            await engine.dispose()
            logger.info("application_stopped")

    app = FastAPI(
        title=settings.app_name,
        lifespan=lifespan,
    )
    app.include_router(health.router)
    app.include_router(admin.router)
    app.include_router(webhook.router)
    return app


app = create_app()
