from __future__ import annotations

from aiogram import Router
from aiogram.types import CallbackQuery, ErrorEvent, Message

from app.logging import get_logger
from app.utils.exceptions import UserVisibleError

router = Router(name="errors")
logger = get_logger(__name__)


@router.error()
async def on_error(event: ErrorEvent) -> None:
    logger.exception("bot_handler_error", exception=repr(event.exception))
    message = getattr(event.update, "message", None)
    callback_query = getattr(event.update, "callback_query", None)

    if isinstance(event.exception, UserVisibleError):
        if isinstance(message, Message):
            await message.answer(str(event.exception))
            return
        if isinstance(callback_query, CallbackQuery):
            await callback_query.answer(str(event.exception), show_alert=True)
            return

    if isinstance(message, Message):
        await message.answer("Something went wrong. Please try again.")
    elif isinstance(callback_query, CallbackQuery):
        await callback_query.answer("Something went wrong. Please try again.", show_alert=True)
