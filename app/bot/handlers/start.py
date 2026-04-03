from __future__ import annotations

from aiogram import F, Router
from aiogram.enums import ChatType
from aiogram.filters import CommandObject, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import Message

from app.bot.handlers.matchmaking import start_chat_flow
from app.bot.keyboards.common import rules_accept_keyboard
from app.bot.states.registration import RegistrationStates
from app.db.models.user import User
from app.services.match_service import MatchService
from app.services.user_service import UserService
from app.utils.text import RULES_TEXT, WELCOME_TEXT

router = Router(name="start")
router.message.filter(F.chat.type == ChatType.PRIVATE)


@router.message(CommandStart())
async def start_command(
    message: Message,
    state: FSMContext,
    app_user: User | None,
    app_user_created: bool,
    user_service: UserService,
    match_service: MatchService,
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
        await start_chat_flow(message, app_user, match_service)
        return

    await state.set_state(RegistrationStates.awaiting_consent)
    sent_message = await message.answer(
        f"{WELCOME_TEXT}\n\n{RULES_TEXT}",
        reply_markup=rules_accept_keyboard(app_user.telegram_id if app_user is not None else None),
    )
    await state.update_data(prompt_message_id=sent_message.message_id)
