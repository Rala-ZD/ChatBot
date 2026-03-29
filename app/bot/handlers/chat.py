from __future__ import annotations

from aiogram import F, Router
from aiogram.enums import ChatType
from aiogram.filters import Command
from aiogram.types import Message

from app.bot.filters.chat_state import ActiveSessionFilter
from app.bot.keyboards.chat import active_chat_keyboard
from app.bot.keyboards.common import main_menu_keyboard, searching_keyboard
from app.db.models.user import User
from app.services.match_service import MatchService
from app.services.relay_service import RelayService
from app.services.session_service import SessionService
from app.utils.enums import EndReason
from app.utils.text import CHAT_COMMAND_HINT_TEXT, NO_ACTIVE_CHAT_TEXT, SEARCHING_TEXT

router = Router(name="chat")
router.message.filter(F.chat.type == ChatType.PRIVATE)


@router.message(Command("next"))
@router.message(F.text == "Next")
async def next_stranger(
    message: Message,
    app_user: User,
    session_service: SessionService,
    match_service: MatchService,
) -> None:
    result = await session_service.end_active_session_for_user(
        app_user.id,
        EndReason.NEXT,
        ended_by_user_id=app_user.id,
    )
    if result is None:
        if await match_service.is_waiting(app_user.id):
            await message.answer(
                SEARCHING_TEXT,
                reply_markup=searching_keyboard(),
            )
            return
        await message.answer(
            NO_ACTIVE_CHAT_TEXT,
            reply_markup=main_menu_keyboard(),
        )
        return

    outcome = await match_service.start(app_user)
    if outcome.status != "matched":
        await message.answer(
            SEARCHING_TEXT,
            reply_markup=searching_keyboard(),
        )


@router.message(Command("end"))
@router.message(F.text == "End")
async def end_chat(message: Message, app_user: User, session_service: SessionService) -> None:
    result = await session_service.end_active_session_for_user(
        app_user.id,
        EndReason.END,
        ended_by_user_id=app_user.id,
    )
    if result is None:
        await message.answer(
            NO_ACTIVE_CHAT_TEXT,
            reply_markup=main_menu_keyboard(),
        )
        return
    await message.answer("\U0001f44b Chat Ended\nBack to the menu.", reply_markup=main_menu_keyboard())


@router.message(ActiveSessionFilter(required=True))
async def relay_chat_message(message: Message, app_user: User, relay_service: RelayService) -> None:
    if message.text and message.text.startswith("/"):
        await message.answer(CHAT_COMMAND_HINT_TEXT)
        return
    await relay_service.relay_message(app_user, message)
