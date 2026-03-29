from __future__ import annotations

from aiogram import Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage

from app.bot.handlers import admin, chat, common, errors, registration
from app.bot.middlewares.rate_limit import RateLimitMiddleware
from app.bot.middlewares.services import ServicesMiddleware
from app.services.container import ServiceContainer


def create_dispatcher(services: ServiceContainer) -> Dispatcher:
    dispatcher = Dispatcher(storage=MemoryStorage())
    services_middleware = ServicesMiddleware(services)
    rate_limit_middleware = RateLimitMiddleware()

    dispatcher.update.middleware(services_middleware)
    dispatcher.message.middleware(rate_limit_middleware)
    dispatcher.callback_query.middleware(rate_limit_middleware)

    dispatcher.include_router(errors.router)
    dispatcher.include_router(admin.router)
    dispatcher.include_router(registration.router)
    dispatcher.include_router(common.router)
    dispatcher.include_router(chat.router)
    return dispatcher
