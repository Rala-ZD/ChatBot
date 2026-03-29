from __future__ import annotations

from typing import Any, Awaitable, Callable

from aiogram import BaseMiddleware
from aiogram.types import TelegramObject

from app.services.container import ServiceContainer


class ServicesMiddleware(BaseMiddleware):
    def __init__(self, services: ServiceContainer) -> None:
        self.services = services

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        data["services"] = self.services
        data["settings"] = self.services.settings
        return await handler(event, data)
