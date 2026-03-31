from __future__ import annotations

from collections.abc import Sequence

from aiogram import F, Router
from aiogram.enums import ChatType
from aiogram.exceptions import TelegramBadRequest
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from app.bot.keyboards.common import main_menu_keyboard
from app.bot.keyboards.registration import (
    REGISTRATION_INTEREST_OPTIONS,
    gender_keyboard,
    interests_keyboard,
)
from app.bot.states.registration import RegistrationStates
from app.db.models.user import User
from app.schemas.user import RegistrationPayload
from app.services.user_service import UserService
from app.utils.enums import Gender, PreferredGender

router = Router(name="registration")
router.message.filter(F.chat.type == ChatType.PRIVATE)
router.callback_query.filter(F.message.chat.type == ChatType.PRIVATE)

PROMPT_MESSAGE_ID_KEY = "prompt_message_id"
INTERESTS_STATE_KEY = "interests"
AGE_PROMPT_TEXT = "How old are you?"
GENDER_PROMPT_TEXT = "Select your gender."
INTERESTS_PROMPT_TEXT = "Choose a few interests, or tap Skip."
REGISTRATION_SUCCESS_TEXT = "Profile saved.\nYou're ready to chat."
INTEREST_SLUGS = {slug for slug, _ in REGISTRATION_INTEREST_OPTIONS}


@router.callback_query(F.data == "register:consent", RegistrationStates.awaiting_consent)
async def accept_rules(callback: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(RegistrationStates.awaiting_age)
    await _edit_or_replace_prompt(
        callback,
        state,
        AGE_PROMPT_TEXT,
    )
    await callback.answer()


@router.message(RegistrationStates.awaiting_age)
async def collect_age(message: Message, state: FSMContext, user_service: UserService) -> None:
    age = user_service.parse_age(message.text or "")
    await state.update_data(age=age)
    await state.set_state(RegistrationStates.awaiting_gender)
    await _delete_tracked_prompt(message, state)
    await _delete_message(message)
    prompt_message = await message.answer(
        GENDER_PROMPT_TEXT,
        reply_markup=gender_keyboard(),
    )
    await state.update_data(prompt_message_id=prompt_message.message_id)


@router.callback_query(
    F.data.startswith("register:gender:"),
    RegistrationStates.awaiting_gender,
)
async def collect_gender(callback: CallbackQuery, state: FSMContext) -> None:
    value = callback.data.rsplit(":", maxsplit=1)[-1]
    await state.update_data(
        gender=Gender(value).value,
        interests=[],
    )
    await state.set_state(RegistrationStates.awaiting_interests)
    await _edit_or_replace_prompt(
        callback,
        state,
        INTERESTS_PROMPT_TEXT,
        reply_markup=interests_keyboard(),
    )
    await callback.answer()


@router.callback_query(
    F.data.startswith("register:interest:toggle:"),
    RegistrationStates.awaiting_interests,
)
async def toggle_interest(callback: CallbackQuery, state: FSMContext) -> None:
    slug = callback.data.rsplit(":", maxsplit=1)[-1]
    if slug not in INTEREST_SLUGS:
        await callback.answer()
        return

    selected = set(await _selected_interests(state))
    if slug in selected:
        selected.remove(slug)
    else:
        selected.add(slug)

    ordered_selection = [
        option_slug
        for option_slug, _ in REGISTRATION_INTEREST_OPTIONS
        if option_slug in selected
    ]
    await state.update_data(interests=ordered_selection)
    if callback.message is not None:
        try:
            await callback.message.edit_text(
                INTERESTS_PROMPT_TEXT,
                reply_markup=interests_keyboard(ordered_selection),
            )
        except TelegramBadRequest:
            pass
    await callback.answer()


@router.callback_query(
    F.data == "register:interest:skip",
    RegistrationStates.awaiting_interests,
)
async def skip_interests(
    callback: CallbackQuery,
    state: FSMContext,
    app_user: User,
    user_service: UserService,
) -> None:
    await state.update_data(interests=[])
    await _finish_registration(callback, state, app_user, user_service)
    await callback.answer()


@router.callback_query(
    F.data == "register:interest:done",
    RegistrationStates.awaiting_interests,
)
async def finish_interests(
    callback: CallbackQuery,
    state: FSMContext,
    app_user: User,
    user_service: UserService,
) -> None:
    await _finish_registration(callback, state, app_user, user_service)
    await callback.answer()


async def _finish_registration(
    callback: CallbackQuery,
    state: FSMContext,
    app_user: User,
    user_service: UserService,
) -> None:
    data = await state.get_data()
    payload = RegistrationPayload(
        age=data["age"],
        gender=data["gender"],
        nickname=None,
        preferred_gender=PreferredGender.ANY,
        interests=data.get(INTERESTS_STATE_KEY, []),
        consented=True,
    )
    await user_service.register_user(app_user, payload)
    await _delete_current_prompt(callback)
    await state.clear()
    if callback.message is not None:
        await callback.message.answer(
            REGISTRATION_SUCCESS_TEXT,
            reply_markup=main_menu_keyboard(),
        )


async def _selected_interests(state: FSMContext) -> list[str]:
    data = await state.get_data()
    interests = data.get(INTERESTS_STATE_KEY, [])
    if isinstance(interests, Sequence) and not isinstance(interests, str):
        return [str(item) for item in interests]
    return []


async def _edit_or_replace_prompt(
    callback: CallbackQuery,
    state: FSMContext,
    text: str,
    *,
    reply_markup: object | None = None,
) -> None:
    if callback.message is None:
        return

    try:
        await callback.message.edit_text(text, reply_markup=reply_markup)
        await state.update_data(prompt_message_id=callback.message.message_id)
        return
    except TelegramBadRequest:
        pass

    await _delete_current_prompt(callback)
    prompt_message = await callback.message.answer(text, reply_markup=reply_markup)
    await state.update_data(prompt_message_id=prompt_message.message_id)


async def _delete_tracked_prompt(message: Message, state: FSMContext) -> None:
    prompt_message_id = (await state.get_data()).get(PROMPT_MESSAGE_ID_KEY)
    if prompt_message_id is None:
        return
    try:
        await message.bot.delete_message(
            chat_id=message.chat.id,
            message_id=prompt_message_id,
        )
    except TelegramBadRequest:
        pass
    await state.update_data(prompt_message_id=None)


async def _delete_current_prompt(callback: CallbackQuery) -> None:
    if callback.message is None:
        return
    await _delete_message(callback.message)


async def _delete_message(message: Message) -> None:
    try:
        await message.delete()
    except TelegramBadRequest:
        pass
