from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

from aiogram import BaseMiddleware
from aiogram.types import CallbackQuery, Message
from redis.asyncio import Redis

from app.config import Settings


class ThrottlingMiddleware(BaseMiddleware):
    def __init__(self, redis: Redis, settings: Settings) -> None:
        self.redis = redis
        self.settings = settings

    async def __call__(
        self,
        handler: Callable[[Any, dict[str, Any]], Awaitable[Any]],
        event: Any,
        data: dict[str, Any],
    ) -> Any:
        user = data.get("event_from_user")
        if user is None:
            return await handler(event, data)

        scope, limit = self._resolve_scope_and_limit(event)
        key = f"throttle:{scope}:{user.id}"
        current = await self.redis.incr(key)
        if current == 1:
            await self.redis.expire(key, 10)
        if current > limit:
            await self._notify_limit(event)
            return None
        return await handler(event, data)

    def _resolve_scope_and_limit(self, event: Any) -> tuple[str, int]:
        if isinstance(event, CallbackQuery):
            return "commands", self.settings.rate_limit_commands
        if isinstance(event, Message) and event.text and event.text.startswith("/"):
            return "commands", self.settings.rate_limit_commands
        return "messages", self.settings.rate_limit_messages

    async def _notify_limit(self, event: Any) -> None:
        text = "You’re sending actions too quickly. Please slow down for a moment."
        if isinstance(event, CallbackQuery):
            await event.answer(text, show_alert=True)
        elif isinstance(event, Message):
            await event.answer(text)
