from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

from aiogram import BaseMiddleware
from aiogram.types import CallbackQuery, Message

from app.logging import get_logger
from app.services.ops_service import OpsService
from app.services.exceptions import ServiceError


class ErrorHandlerMiddleware(BaseMiddleware):
    def __init__(self, ops_service: OpsService) -> None:
        self.logger = get_logger(__name__)
        self.ops_service = ops_service

    async def __call__(
        self,
        handler: Callable[[Any, dict[str, Any]], Awaitable[Any]],
        event: Any,
        data: dict[str, Any],
    ) -> Any:
        try:
            return await handler(event, data)
        except ServiceError as exc:
            await self._reply(event, str(exc))
        except Exception as exc:  # pragma: no cover
            await self.ops_service.record_handler_failure()
            self.logger.exception("bot_handler_error", error=str(exc))
            await self._reply(event, "Something went wrong. Please try again.")
        return None

    async def _reply(self, event: Any, text: str) -> None:
        if isinstance(event, Message):
            await event.answer(text)
        elif isinstance(event, CallbackQuery):
            await event.answer(text, show_alert=True)
            if event.message:
                await event.message.answer(text)
