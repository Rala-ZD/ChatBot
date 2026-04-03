from __future__ import annotations

import asyncio
import contextlib
from contextlib import asynccontextmanager

from aiogram import Bot
from fastapi import FastAPI
from redis.asyncio import Redis

from app.api.health import router as health_router
from app.api.ops import router as ops_router
from app.api.telegram import router as telegram_router
from app.bot.commands import register_bot_commands
from app.bot.dispatcher import create_dispatcher
from app.config import Settings, get_settings
from app.db.session import create_engine, create_session_factory
from app.logging import configure_logging, get_logger
from app.services.ops_service import OpsService


def create_app(settings: Settings | None = None) -> FastAPI:
    app_settings = settings or get_settings()
    configure_logging(app_settings.log_level)
    logger = get_logger(__name__)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        engine = create_engine(app_settings.postgres_dsn)
        session_factory = create_session_factory(engine)
        redis = Redis.from_url(app_settings.redis_dsn, decode_responses=True)
        bot = Bot(token=app_settings.bot_token)
        dispatcher = create_dispatcher(app_settings, session_factory, redis, bot)
        ops_service = OpsService(redis, app_settings)

        app.state.settings = app_settings
        app.state.engine = engine
        app.state.session_factory = session_factory
        app.state.redis = redis
        app.state.bot = bot
        app.state.dispatcher = dispatcher
        app.state.ops_service = ops_service

        polling_task: asyncio.Task[None] | None = None

        try:
            await register_bot_commands(bot)
            if app_settings.bot_delivery_mode == "polling":
                await bot.delete_webhook(drop_pending_updates=False)
                polling_task = asyncio.create_task(dispatcher.start_polling(bot))
                logger.info("bot_runtime_started", delivery_mode="polling")
            else:
                await bot.set_webhook(
                    url=app_settings.webhook_url,
                    allowed_updates=dispatcher.resolve_used_update_types(),
                    drop_pending_updates=False,
                    secret_token=app_settings.webhook_secret,
                )
                logger.info("bot_runtime_started", delivery_mode="webhook")
            yield
        finally:
            if polling_task is not None:
                polling_task.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await polling_task
            await dispatcher.storage.close()
            await bot.session.close()
            await redis.aclose()
            await engine.dispose()

    app = FastAPI(title="Telegram Anonymous Chat Bot", lifespan=lifespan)
    app.include_router(health_router)
    app.include_router(ops_router)
    app.include_router(telegram_router, prefix=app_settings.webhook_path)
    return app


app = create_app()
