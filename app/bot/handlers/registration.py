from __future__ import annotations

from collections.abc import Sequence

from aiogram import F, Router
from aiogram.enums import ChatType
from aiogram.exceptions import TelegramBadRequest
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from app.bot.keyboards.common import main_menu_keyboard
from app.bot.keyboards.registration import (
    REGISTRATION_AGE_OPTIONS,
    REGISTRATION_INTEREST_OPTIONS,
    REGISTRATION_REGION_OPTIONS,
    age_keyboard,
    gender_keyboard,
    interests_keyboard,
    region_keyboard,
)
from app.bot.states.registration import RegistrationStates
from app.db.models.user import User
from app.schemas.user import RegistrationPayload
from app.services.user_service import UserService
from app.utils.enums import Gender, PreferredGender
from app.utils.text import REGISTRATION_STEP_UNAVAILABLE_TEXT

router = Router(name="registration")
router.message.filter(F.chat.type == ChatType.PRIVATE)
router.callback_query.filter(F.message.chat.type == ChatType.PRIVATE)

PROMPT_MESSAGE_ID_KEY = "prompt_message_id"
INTERESTS_STATE_KEY = "interests"
MATCH_REGION_STATE_KEY = "match_region"
AGE_PROMPT_TEXT = "ℹ️ What is your age?"
GENDER_PROMPT_TEXT = "Select your gender."
REGION_PROMPT_TEXT = "🌐 Choose your preferred chat region"
INTERESTS_PROMPT_TEXT = "Choose a few interests, or tap Skip."
REGISTRATION_SUCCESS_TEXT = "Profile saved.\nYou're ready to chat."
INTEREST_SLUGS = {slug for slug, _ in REGISTRATION_INTEREST_OPTIONS}
AGE_BUCKETS = {
    "under18": 17,
    "18_21": 18,
    "22_25": 22,
    "26_45": 26,
}
AGE_BUCKET_SLUGS = {slug for slug, _ in REGISTRATION_AGE_OPTIONS}
REGION_SLUGS = {slug for slug, _ in REGISTRATION_REGION_OPTIONS}


def _extract_owner_telegram_id(data: str | None) -> int | None:
    if data is None:
        return None
    try:
        return int(data.rsplit(":", maxsplit=1)[-1])
    except (TypeError, ValueError):
        return None


async def _ensure_callback_owner(callback: CallbackQuery, app_user: User) -> bool:
    owner_telegram_id = _extract_owner_telegram_id(callback.data)
    from_user = callback.from_user
    if (
        from_user is None
        or owner_telegram_id is None
        or from_user.id != owner_telegram_id
        or app_user.telegram_id != from_user.id
    ):
        await callback.answer(REGISTRATION_STEP_UNAVAILABLE_TEXT, show_alert=True)
        return False
    return True


def _owned_value(callback_data: str, prefix: str) -> str | None:
    owned_prefix = f"{prefix}:"
    if not callback_data.startswith(owned_prefix):
        return None

    suffix = callback_data[len(owned_prefix) :]
    value, separator, owner_text = suffix.rpartition(":")
    if not separator or not owner_text:
        return None
    return value or None


@router.callback_query(F.data.startswith("register:consent"), RegistrationStates.awaiting_consent)
async def accept_rules(callback: CallbackQuery, state: FSMContext, app_user: User) -> None:
    if not await _ensure_callback_owner(callback, app_user):
        return
    await state.set_state(RegistrationStates.awaiting_age)
    await _edit_or_replace_prompt(
        callback,
        state,
        AGE_PROMPT_TEXT,
        reply_markup=age_keyboard(owner_telegram_id=app_user.telegram_id),
    )
    await callback.answer()


@router.callback_query(
    F.data.startswith("register:age:"),
    RegistrationStates.awaiting_age,
)
async def collect_age(
    callback: CallbackQuery,
    state: FSMContext,
    app_user: User,
    user_service: UserService,
) -> None:
    if not await _ensure_callback_owner(callback, app_user):
        return

    slug = _owned_value(callback.data, "register:age")
    if slug not in AGE_BUCKET_SLUGS:
        await callback.answer()
        return

    age = user_service.parse_age(str(AGE_BUCKETS[slug]))
    await state.update_data(age=age)
    await state.set_state(RegistrationStates.awaiting_gender)
    await _edit_or_replace_prompt(
        callback,
        state,
        GENDER_PROMPT_TEXT,
        reply_markup=gender_keyboard(owner_telegram_id=app_user.telegram_id),
    )
    await callback.answer()


@router.message(RegistrationStates.awaiting_age)
async def ignore_typed_age(message: Message) -> None:
    await _delete_message(message)


@router.callback_query(
    F.data.startswith("register:gender:"),
    RegistrationStates.awaiting_gender,
)
async def collect_gender(
    callback: CallbackQuery,
    state: FSMContext,
    app_user: User,
) -> None:
    if not await _ensure_callback_owner(callback, app_user):
        return

    value = _owned_value(callback.data, "register:gender")
    if value is None:
        await callback.answer()
        return

    try:
        gender = Gender(value)
    except ValueError:
        await callback.answer()
        return

    await state.update_data(
        gender=gender.value,
        interests=[],
    )
    await state.set_state(RegistrationStates.awaiting_region)
    await _edit_or_replace_prompt(
        callback,
        state,
        REGION_PROMPT_TEXT,
        reply_markup=region_keyboard(owner_telegram_id=app_user.telegram_id),
    )
    await callback.answer()


@router.callback_query(
    F.data.startswith("register:region:back:"),
    RegistrationStates.awaiting_region,
)
async def return_to_gender_from_region(
    callback: CallbackQuery,
    state: FSMContext,
    app_user: User,
) -> None:
    if not await _ensure_callback_owner(callback, app_user):
        return

    await state.set_state(RegistrationStates.awaiting_gender)
    await _edit_or_replace_prompt(
        callback,
        state,
        GENDER_PROMPT_TEXT,
        reply_markup=gender_keyboard(owner_telegram_id=app_user.telegram_id),
    )
    await callback.answer()


@router.callback_query(
    F.data.startswith("register:region:"),
    RegistrationStates.awaiting_region,
)
async def collect_region(
    callback: CallbackQuery,
    state: FSMContext,
    app_user: User,
) -> None:
    if not await _ensure_callback_owner(callback, app_user):
        return

    slug = _owned_value(callback.data, "register:region")
    if slug not in REGION_SLUGS:
        await callback.answer()
        return

    await state.update_data(**{MATCH_REGION_STATE_KEY: slug})
    await state.set_state(RegistrationStates.awaiting_interests)
    await _edit_or_replace_prompt(
        callback,
        state,
        INTERESTS_PROMPT_TEXT,
        reply_markup=interests_keyboard(owner_telegram_id=app_user.telegram_id),
    )
    await callback.answer()


@router.callback_query(
    F.data.startswith("register:interest:toggle:"),
    RegistrationStates.awaiting_interests,
)
async def toggle_interest(callback: CallbackQuery, state: FSMContext, app_user: User) -> None:
    if not await _ensure_callback_owner(callback, app_user):
        return

    slug = _owned_value(callback.data, "register:interest:toggle")
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
                reply_markup=interests_keyboard(
                    ordered_selection,
                    owner_telegram_id=app_user.telegram_id,
                ),
            )
        except TelegramBadRequest:
            pass
    await callback.answer()


@router.callback_query(
    F.data.startswith("register:interest:skip"),
    RegistrationStates.awaiting_interests,
)
async def skip_interests(
    callback: CallbackQuery,
    state: FSMContext,
    app_user: User,
    user_service: UserService,
) -> None:
    if not await _ensure_callback_owner(callback, app_user):
        return
    await state.update_data(interests=[])
    await _finish_registration(callback, state, app_user, user_service)
    await callback.answer()


@router.callback_query(
    F.data.startswith("register:interest:done"),
    RegistrationStates.awaiting_interests,
)
async def finish_interests(
    callback: CallbackQuery,
    state: FSMContext,
    app_user: User,
    user_service: UserService,
) -> None:
    if not await _ensure_callback_owner(callback, app_user):
        return
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
        match_region=data.get(MATCH_REGION_STATE_KEY),
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


async def _delete_current_prompt(callback: CallbackQuery) -> None:
    if callback.message is None:
        return
    await _delete_message(callback.message)


async def _delete_message(message: Message) -> None:
    try:
        await message.delete()
    except TelegramBadRequest:
        pass
