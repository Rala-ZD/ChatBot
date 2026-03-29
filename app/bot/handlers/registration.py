from __future__ import annotations

from aiogram import F, Router
from aiogram.enums import ChatType
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from app.bot.keyboards.common import confirm_keyboard, main_menu_keyboard
from app.bot.keyboards.registration import (
    gender_keyboard,
    preferred_gender_keyboard,
    skip_keyboard,
)
from app.bot.states.registration import RegistrationStates
from app.db.models.user import User
from app.schemas.user import RegistrationPayload
from app.services.user_service import UserService
from app.utils.enums import Gender, PreferredGender
from app.utils.text import format_preferred_gender

router = Router(name="registration")
router.message.filter(F.chat.type == ChatType.PRIVATE)
router.callback_query.filter(F.message.chat.type == ChatType.PRIVATE)


@router.callback_query(F.data == "register:consent", RegistrationStates.awaiting_consent)
async def accept_rules(callback: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(RegistrationStates.awaiting_age)
    await callback.message.answer("How old are you?")
    await callback.answer()


@router.message(RegistrationStates.awaiting_age)
async def collect_age(message: Message, state: FSMContext, user_service: UserService) -> None:
    age = user_service.parse_age(message.text or "")
    await state.update_data(age=age)
    await state.set_state(RegistrationStates.awaiting_gender)
    await message.answer("Select your gender.", reply_markup=gender_keyboard())


@router.callback_query(
    F.data.startswith("register:gender:"),
    RegistrationStates.awaiting_gender,
)
async def collect_gender(callback: CallbackQuery, state: FSMContext) -> None:
    value = callback.data.rsplit(":", maxsplit=1)[-1]
    await state.update_data(gender=Gender(value).value)
    await state.set_state(RegistrationStates.awaiting_nickname)
    await callback.message.answer(
        "Add a nickname, or skip.",
        reply_markup=skip_keyboard("register:skip:nickname"),
    )
    await callback.answer()


@router.callback_query(
    F.data == "register:skip:nickname",
    RegistrationStates.awaiting_nickname,
)
async def skip_nickname(callback: CallbackQuery, state: FSMContext) -> None:
    await state.update_data(nickname=None)
    await state.set_state(RegistrationStates.awaiting_preferred_gender)
    await callback.message.answer(
        "Choose your filter.\nPremium matching only.",
        reply_markup=preferred_gender_keyboard(),
    )
    await callback.answer()


@router.message(RegistrationStates.awaiting_nickname)
async def collect_nickname(message: Message, state: FSMContext, user_service: UserService) -> None:
    nickname = user_service.normalize_nickname(message.text or "")
    await state.update_data(nickname=nickname)
    await state.set_state(RegistrationStates.awaiting_preferred_gender)
    await message.answer(
        "Choose your filter.\nPremium matching only.",
        reply_markup=preferred_gender_keyboard(),
    )


@router.callback_query(
    F.data.startswith("register:preferred:"),
    RegistrationStates.awaiting_preferred_gender,
)
async def collect_preferred_gender(callback: CallbackQuery, state: FSMContext) -> None:
    value = callback.data.rsplit(":", maxsplit=1)[-1]
    await state.update_data(preferred_gender=PreferredGender(value).value)
    await state.set_state(RegistrationStates.awaiting_interests)
    await callback.message.answer(
        "Add interests, or skip.",
        reply_markup=skip_keyboard("register:skip:interests"),
    )
    await callback.answer()


@router.callback_query(
    F.data == "register:skip:interests",
    RegistrationStates.awaiting_interests,
)
async def skip_interests(callback: CallbackQuery, state: FSMContext) -> None:
    await state.update_data(interests=[])
    await _show_confirmation(callback.message, state)
    await callback.answer()


@router.message(RegistrationStates.awaiting_interests)
async def collect_interests(message: Message, state: FSMContext, user_service: UserService) -> None:
    interests = user_service.normalize_interests(message.text or "")
    await state.update_data(interests=interests)
    await _show_confirmation(message, state)


@router.callback_query(F.data == "register:confirm", RegistrationStates.awaiting_confirmation)
async def confirm_registration(
    callback: CallbackQuery,
    state: FSMContext,
    app_user: User,
    user_service: UserService,
) -> None:
    payload = RegistrationPayload(**await state.get_data(), consented=True)
    await user_service.register_user(app_user, payload)
    await state.clear()
    await callback.message.answer(
        "Profile saved.\nYou're ready to chat.",
        reply_markup=main_menu_keyboard(),
    )
    await callback.answer()


@router.callback_query(F.data == "register:edit", RegistrationStates.awaiting_confirmation)
async def edit_registration(callback: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(RegistrationStates.awaiting_age)
    await callback.message.answer("Let's update your profile.\nHow old are you?")
    await callback.answer()


async def _show_confirmation(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    summary = (
        "\U0001f464 Profile\n\n"
        f"Age: {data['age']}\n"
        f"Gender: {data['gender'].title()}\n"
        f"Nick: {data.get('nickname') or 'Not set'}\n"
        f"Filter: {format_preferred_gender(data.get('preferred_gender', 'any'))}\n"
        f"Interests: {', '.join(data.get('interests', [])) or 'Not set'}"
    )
    await state.set_state(RegistrationStates.awaiting_confirmation)
    await message.answer(
        summary,
        reply_markup=confirm_keyboard("register:confirm", "register:edit"),
    )
