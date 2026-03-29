from __future__ import annotations

from aiogram import F, Router
from aiogram.enums import ChatType
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import Message

from app.bot.keyboards.chat import active_chat_keyboard
from app.bot.keyboards.common import main_menu_keyboard
from app.db.models.user import User
from app.services.match_service import MatchService
from app.services.session_service import SessionService
from app.utils.text import (
    HELP_TEXT,
    NO_ACTIVE_SEARCH_TEXT,
    RULES_TEXT,
    SEARCH_CANCEL_BUTTON_TEXT,
    SEARCH_CANCELLED_TEXT,
    SEARCH_MATCHED_TEXT,
)

router = Router(name="menu")
router.message.filter(F.chat.type == ChatType.PRIVATE)


@router.message(Command("help"))
@router.message(F.text == "Help")
async def help_message(message: Message) -> None:
    await message.answer(HELP_TEXT, reply_markup=main_menu_keyboard())


@router.message(F.text == "Safety")
async def rules_message(message: Message) -> None:
    await message.answer(RULES_TEXT, reply_markup=main_menu_keyboard())


@router.message(Command("cancel"))
@router.message(F.text == SEARCH_CANCEL_BUTTON_TEXT)
async def cancel_action(
    message: Message,
    state: FSMContext,
    app_user: User | None,
    match_service: MatchService,
    session_service: SessionService,
) -> None:
    current_state = await state.get_state()
    if current_state:
        await state.clear()
        await message.answer("Cancelled.", reply_markup=main_menu_keyboard())
        return

    if app_user is None:
        await message.answer(NO_ACTIVE_SEARCH_TEXT, reply_markup=main_menu_keyboard())
        return

    active_session = await session_service.get_active_session_for_user(app_user.id)
    if active_session is not None:
        if message.text == SEARCH_CANCEL_BUTTON_TEXT:
            await message.answer(SEARCH_MATCHED_TEXT, reply_markup=active_chat_keyboard())
        else:
            await message.answer("Use /end or /next in chat.", reply_markup=active_chat_keyboard())
        return

    cancelled = await match_service.cancel_waiting(app_user.id)
    if cancelled:
        await message.answer(SEARCH_CANCELLED_TEXT, reply_markup=main_menu_keyboard())
        return

    active_session = await session_service.get_active_session_for_user(app_user.id)
    if active_session is not None:
        if message.text == SEARCH_CANCEL_BUTTON_TEXT:
            await message.answer(SEARCH_MATCHED_TEXT, reply_markup=active_chat_keyboard())
        else:
            await message.answer("Use /end or /next in chat.", reply_markup=active_chat_keyboard())
        return

    await message.answer(NO_ACTIVE_SEARCH_TEXT, reply_markup=main_menu_keyboard())
