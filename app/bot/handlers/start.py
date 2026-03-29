from __future__ import annotations

from aiogram import F, Router
from aiogram.enums import ChatType
from aiogram.filters import CommandObject, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import Message

from app.bot.keyboards.common import main_menu_keyboard, rules_accept_keyboard
from app.bot.states.registration import RegistrationStates
from app.db.models.user import User
from app.services.user_service import UserService
from app.utils.text import RETURNING_HOME_TEXT, RULES_TEXT, WELCOME_TEXT

router = Router(name="start")
router.message.filter(F.chat.type == ChatType.PRIVATE)


@router.message(CommandStart())
async def start_command(
    message: Message,
    state: FSMContext,
    app_user: User | None,
    app_user_created: bool,
    user_service: UserService,
    command: CommandObject | None = None,
) -> None:
    await state.clear()

    if app_user is not None:
        await user_service.apply_referral_code_if_eligible(
            app_user,
            command.args if command else None,
            is_new_user=app_user_created,
        )

    if app_user and app_user.is_registered:
        await message.answer(
            RETURNING_HOME_TEXT,
            reply_markup=main_menu_keyboard(),
        )
        return

    await state.set_state(RegistrationStates.awaiting_consent)
    await message.answer(
        f"{WELCOME_TEXT}\n\n{RULES_TEXT}",
        reply_markup=rules_accept_keyboard(),
    )
