from __future__ import annotations

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import Message

from app.bot.keyboards.menus import main_menu_keyboard, registration_start_keyboard
from app.services.container import ServiceContainer
from app.utils.constants import (
    MAIN_MENU_EDIT_PROFILE,
    MAIN_MENU_HELP,
    MAIN_MENU_RULES,
)

router = Router(name="common")

RULES_TEXT = (
    "<b>Rules</b>\n"
    "1. Be respectful.\n"
    "2. Do not share explicit, abusive, or illegal content.\n"
    "3. Do not attempt to identify or harass other users.\n"
    "4. Reports and bans are enforced.\n"
    "5. You must meet the minimum age requirement."
)

HELP_TEXT = (
    "<b>Help</b>\n"
    "Use Start Chat to find a stranger.\n"
    "Use /next to skip, /end to leave, and /report to report abuse.\n"
    "Use /profile to update your details.\n"
    "Use /cancel to exit a form or stop waiting in queue.\n"
    "Need assistance? Contact @{support_username}."
)

WELCOME_TEXT = (
    "<b>Anonymous Stranger Chat</b>\n"
    "Meet real people through an anonymous 1-to-1 relay. "
    "Your identity stays hidden unless you choose to share it.\n\n"
    "Before you can chat, complete a quick registration and accept the safety rules."
)


@router.message(Command("start"))
async def start_command(
    message: Message,
    services: ServiceContainer,
) -> None:
    await services.user_service.sync_telegram_user(message.from_user)
    user = await services.user_service.get_by_telegram_id(message.from_user.id)
    if user and user.is_registered:
        await message.answer(
            "Welcome back. Ready when you are.",
            reply_markup=main_menu_keyboard(),
        )
        return
    await message.answer(WELCOME_TEXT, reply_markup=registration_start_keyboard())


@router.message(Command("help"))
@router.message(F.text == MAIN_MENU_HELP)
async def help_command(
    message: Message,
    services: ServiceContainer,
) -> None:
    await services.user_service.sync_telegram_user(message.from_user)
    help_text = HELP_TEXT.format(support_username=services.settings.support_username)
    await message.answer(help_text, reply_markup=main_menu_keyboard())


@router.message(Command("rules"))
@router.message(F.text == MAIN_MENU_RULES)
async def rules_command(
    message: Message,
    services: ServiceContainer,
) -> None:
    await services.user_service.sync_telegram_user(message.from_user)
    await message.answer(RULES_TEXT, reply_markup=main_menu_keyboard())


@router.message(Command("profile"))
@router.message(F.text == MAIN_MENU_EDIT_PROFILE)
async def profile_command(
    message: Message,
    services: ServiceContainer,
) -> None:
    await services.user_service.sync_telegram_user(message.from_user)
    user = await services.user_service.require_registered_user(message.from_user.id)
    from app.bot.keyboards.menus import profile_keyboard

    await message.answer(
        services.user_service.format_profile(user),
        reply_markup=profile_keyboard(),
    )


@router.message(Command("cancel"))
async def cancel_command(
    message: Message,
    state: FSMContext,
    services: ServiceContainer,
) -> None:
    current_state = await state.get_state()
    if current_state:
        await state.clear()
        await message.answer("Cancelled.", reply_markup=main_menu_keyboard())
        return

    if await services.match_service.cancel_waiting(message.from_user.id):
        await message.answer("Search cancelled.", reply_markup=main_menu_keyboard())
        return

    await message.answer("There is nothing to cancel right now.", reply_markup=main_menu_keyboard())
