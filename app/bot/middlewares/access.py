from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

from aiogram import BaseMiddleware
from aiogram.enums import ChatType

from app.services.user_service import UserService


class AccessMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[Any, dict[str, Any]], Awaitable[Any]],
        event: Any,
        data: dict[str, Any],
    ) -> Any:
        user_service: UserService = data["user_service"]
        event_from_user = data.get("event_from_user")
        event_chat = data.get("event_chat")

        if event_from_user is not None and event_chat is not None and event_chat.type == ChatType.PRIVATE:
            result = await user_service.ensure_telegram_user(event_from_user)
            data["app_user"] = result.user
            data["app_user_created"] = result.created
        else:
            data["app_user"] = None
            data["app_user_created"] = False

        return await handler(event, data)
