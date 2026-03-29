from __future__ import annotations

from typing import Any, Awaitable, Callable

from aiogram import BaseMiddleware
from aiogram.types import CallbackQuery, Message, TelegramObject

from app.services.container import ServiceContainer
from app.utils.redis_keys import rate_limit_key


class RateLimitMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        services: ServiceContainer = data["services"]
        user_id = None
        scope = "command"
        limit = services.settings.command_rate_limit

        if isinstance(event, Message) and event.from_user:
            user_id = event.from_user.id
            if event.text and not event.text.startswith("/"):
                scope = "message"
                limit = services.settings.message_rate_limit
        elif isinstance(event, CallbackQuery) and event.from_user:
            user_id = event.from_user.id

        if user_id is None:
            return await handler(event, data)

        allowed = await services.rate_limiter.hit(rate_limit_key(scope, user_id), limit)
        if allowed:
            return await handler(event, data)

        if isinstance(event, CallbackQuery):
            await event.answer("Too many requests. Please slow down.", show_alert=True)
            return None
        if isinstance(event, Message):
            await event.answer("Too many requests. Please slow down for a moment.")
            return None
        return None
