from __future__ import annotations

from collections.abc import Sequence

from aiogram import F, Router
from aiogram.enums import ChatType
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from app.bot.keyboards.profile import (
    profile_edit_keyboard,
    profile_filter_keyboard,
    profile_gender_keyboard,
    profile_interests_keyboard,
)
from app.bot.keyboards.registration import REGISTRATION_INTEREST_OPTIONS
from app.bot.states.profile import ProfileStates
from app.db.models.user import User
from app.services.exceptions import ValidationError
from app.services.user_service import UserService
from app.utils.enums import Gender, PreferredGender
from app.utils.text import format_interests, format_preferred_gender

router = Router(name="profile")
router.message.filter(F.chat.type == ChatType.PRIVATE)
router.callback_query.filter(F.message.chat.type == ChatType.PRIVATE)

PROFILE_CARD_MESSAGE_ID_KEY = "profile_card_message_id"
PROFILE_EDITOR_MESSAGE_ID_KEY = "profile_editor_message_id"
PROFILE_INTERESTS_KEY = "profile_interests"
PROFILE_EDITOR_HEADING_TEXT = "\u270f\ufe0f Edit Profile"
PROFILE_EDITOR_UNAVAILABLE_TEXT = "\u26a0\ufe0f This profile editor is no longer available"
PROFILE_AGE_PROMPT_TEXT = "Send your age"
PROFILE_NICKNAME_PROMPT_TEXT = "Send your nickname"
PROFILE_GENDER_PROMPT_TEXT = "Select your gender"
PROFILE_FILTER_PROMPT_TEXT = "Choose your filter"
PROFILE_INTERESTS_PROMPT_TEXT = "Choose your interests, then tap Done."
PROFILE_SEPARATOR = "\u2500" * 16
PROFILE_INTEREST_SLUGS = {slug for slug, _ in REGISTRATION_INTEREST_OPTIONS}
PROFILE_STATE_NAMES = {
    ProfileStates.editing_age.state,
    ProfileStates.editing_gender.state,
    ProfileStates.editing_nickname.state,
    ProfileStates.editing_preferred_gender.state,
    ProfileStates.editing_interests.state,
}


def _extract_owner_telegram_id(data: str | None) -> int | None:
    if data is None:
        return None
    try:
        return int(data.rsplit(":", maxsplit=1)[-1])
    except (TypeError, ValueError):
        return None


def _owned_value(callback_data: str | None, prefix: str) -> str | None:
    if callback_data is None:
        return None
    owned_prefix = f"{prefix}:"
    if not callback_data.startswith(owned_prefix):
        return None

    suffix = callback_data[len(owned_prefix) :]
    value, separator, owner_text = suffix.rpartition(":")
    if not separator or not owner_text:
        return None
    return value or None


@router.message(Command("profile"))
@router.message(F.text == "Profile")
async def show_profile(message: Message, state: FSMContext, app_user: User | None) -> None:
    if app_user is None or not app_user.is_registered:
        raise ValidationError("Finish setup with /start first.")
    await _show_profile_screen(message, state, app_user)


@router.callback_query(F.data.startswith("profile:edit:"))
async def start_profile_edit(
    callback: CallbackQuery,
    state: FSMContext,
    app_user: User | None,
) -> None:
    if app_user is None or not app_user.is_registered:
        raise ValidationError("Finish setup with /start first.")
    if not await _ensure_profile_editor_callback(callback, state, app_user):
        return

    field = _owned_value(callback.data, "profile:edit")
    if field == "age":
        await state.set_state(ProfileStates.editing_age)
        await _edit_profile_editor_panel(callback.message, state, app_user, PROFILE_AGE_PROMPT_TEXT)
    elif field == "gender":
        await state.set_state(ProfileStates.editing_gender)
        await _edit_profile_editor_panel(
            callback.message,
            state,
            app_user,
            PROFILE_GENDER_PROMPT_TEXT,
            reply_markup=profile_gender_keyboard(app_user.telegram_id),
        )
    elif field == "nickname":
        await state.set_state(ProfileStates.editing_nickname)
        await _edit_profile_editor_panel(callback.message, state, app_user, PROFILE_NICKNAME_PROMPT_TEXT)
    elif field == "preferred_gender":
        await state.set_state(ProfileStates.editing_preferred_gender)
        await _edit_profile_editor_panel(
            callback.message,
            state,
            app_user,
            PROFILE_FILTER_PROMPT_TEXT,
            reply_markup=profile_filter_keyboard(app_user.telegram_id),
        )
    elif field == "interests":
        await state.set_state(ProfileStates.editing_interests)
        selected = list(app_user.interests_json)
        await state.update_data(**{PROFILE_INTERESTS_KEY: selected})
        await _edit_profile_editor_panel(
            callback.message,
            state,
            app_user,
            PROFILE_INTERESTS_PROMPT_TEXT,
            reply_markup=profile_interests_keyboard(selected, owner_telegram_id=app_user.telegram_id),
        )
    await callback.answer()


@router.message(ProfileStates.editing_age)
async def update_age(
    message: Message,
    state: FSMContext,
    app_user: User,
    user_service: UserService,
) -> None:
    try:
        age = user_service.parse_age(message.text or "")
    except ValidationError as exc:
        await _delete_message(message)
        await _edit_profile_editor_panel(
            message,
            state,
            app_user,
            _profile_prompt_text(PROFILE_AGE_PROMPT_TEXT, error_text=str(exc)),
        )
        return

    updated_user = await user_service.update_profile(app_user, age=age)
    await _delete_message(message)
    await _return_to_profile_screen(message, state, updated_user, "\u2705 Age updated")


@router.message(ProfileStates.editing_nickname)
async def update_nickname(
    message: Message,
    state: FSMContext,
    app_user: User,
    user_service: UserService,
) -> None:
    raw_value = (message.text or "").strip()
    try:
        nickname = None if raw_value.lower() in {"clear", "-"} else user_service.normalize_nickname(raw_value)
    except ValidationError as exc:
        await _delete_message(message)
        await _edit_profile_editor_panel(
            message,
            state,
            app_user,
            _profile_prompt_text(PROFILE_NICKNAME_PROMPT_TEXT, error_text=str(exc)),
        )
        return

    updated_user = await user_service.update_profile(app_user, nickname=nickname)
    await _delete_message(message)
    await _return_to_profile_screen(message, state, updated_user, "\u2705 Nickname updated")


@router.callback_query(F.data.startswith("profile:gender:"), ProfileStates.editing_gender)
async def update_gender(
    callback: CallbackQuery,
    state: FSMContext,
    app_user: User,
    user_service: UserService,
) -> None:
    if not await _ensure_profile_editor_callback(callback, state, app_user):
        return

    value = _owned_value(callback.data, "profile:gender")
    if value is None:
        await callback.answer()
        return

    try:
        gender = Gender(value)
    except ValueError:
        await callback.answer()
        return

    updated_user = await user_service.update_profile(app_user, gender=gender)
    await _return_to_profile_screen(callback.message, state, updated_user, "\u2705 Gender updated")
    await callback.answer()


@router.callback_query(
    F.data.startswith("profile:preferred:"),
    ProfileStates.editing_preferred_gender,
)
async def update_preferred_gender(
    callback: CallbackQuery,
    state: FSMContext,
    app_user: User,
    user_service: UserService,
) -> None:
    if not await _ensure_profile_editor_callback(callback, state, app_user):
        return

    value = _owned_value(callback.data, "profile:preferred")
    if value is None:
        await callback.answer()
        return

    try:
        preferred_gender = PreferredGender(value)
    except ValueError:
        await callback.answer()
        return

    updated_user = await user_service.update_profile(app_user, preferred_gender=preferred_gender)
    await _return_to_profile_screen(callback.message, state, updated_user, "\u2705 Filter updated")
    await callback.answer()


@router.callback_query(
    F.data.startswith("profile:interest:toggle:"),
    ProfileStates.editing_interests,
)
async def toggle_profile_interest(
    callback: CallbackQuery,
    state: FSMContext,
    app_user: User,
) -> None:
    if not await _ensure_profile_editor_callback(callback, state, app_user):
        return

    slug = _owned_value(callback.data, "profile:interest:toggle")
    if slug not in PROFILE_INTEREST_SLUGS:
        await callback.answer()
        return

    selected = set(await _selected_profile_interests(state, app_user))
    if slug in selected:
        selected.remove(slug)
    else:
        selected.add(slug)

    ordered_selection = [
        option_slug
        for option_slug, _ in REGISTRATION_INTEREST_OPTIONS
        if option_slug in selected
    ]
    await state.update_data(**{PROFILE_INTERESTS_KEY: ordered_selection})
    await _edit_profile_editor_panel(
        callback.message,
        state,
        app_user,
        PROFILE_INTERESTS_PROMPT_TEXT,
        reply_markup=profile_interests_keyboard(ordered_selection, owner_telegram_id=app_user.telegram_id),
    )
    await callback.answer()


@router.callback_query(
    F.data.startswith("profile:interest:done"),
    ProfileStates.editing_interests,
)
async def finish_profile_interests(
    callback: CallbackQuery,
    state: FSMContext,
    app_user: User,
    user_service: UserService,
) -> None:
    if not await _ensure_profile_editor_callback(callback, state, app_user):
        return

    updated_user = await user_service.update_profile(
        app_user,
        interests_json=await _selected_profile_interests(state, app_user),
    )
    await _return_to_profile_screen(callback.message, state, updated_user, "\u2705 Interests updated")
    await callback.answer()


async def _ensure_profile_editor_callback(
    callback: CallbackQuery,
    state: FSMContext,
    app_user: User,
) -> bool:
    owner_telegram_id = _extract_owner_telegram_id(callback.data)
    data = await state.get_data()
    editor_message_id = data.get(PROFILE_EDITOR_MESSAGE_ID_KEY)
    from_user = callback.from_user
    if (
        callback.message is None
        or from_user is None
        or owner_telegram_id is None
        or not isinstance(editor_message_id, int)
        or from_user.id != owner_telegram_id
        or app_user.telegram_id != from_user.id
        or callback.message.message_id != editor_message_id
    ):
        await callback.answer(PROFILE_EDITOR_UNAVAILABLE_TEXT, show_alert=True)
        return False
    return True


async def _selected_profile_interests(state: FSMContext, app_user: User) -> list[str]:
    data = await state.get_data()
    selected = data.get(PROFILE_INTERESTS_KEY)
    if isinstance(selected, Sequence) and not isinstance(selected, str):
        return [str(item) for item in selected]
    return [str(item) for item in app_user.interests_json]


async def _show_profile_screen(
    source_message: Message,
    state: FSMContext,
    app_user: User,
    *,
    status_text: str | None = None,
) -> None:
    await _delete_tracked_profile_messages(source_message.bot, source_message.chat.id, state)
    card_message = await source_message.answer(_profile_summary(app_user))
    editor_message = await source_message.answer(
        _profile_editor_panel_text(status_text),
        reply_markup=profile_edit_keyboard(app_user.telegram_id),
    )
    await state.set_state(None)
    await state.update_data(
        **{
            PROFILE_CARD_MESSAGE_ID_KEY: card_message.message_id,
            PROFILE_EDITOR_MESSAGE_ID_KEY: editor_message.message_id,
            PROFILE_INTERESTS_KEY: list(app_user.interests_json),
        }
    )


async def _return_to_profile_screen(
    source_message: Message | None,
    state: FSMContext,
    app_user: User,
    status_text: str,
) -> None:
    if source_message is None:
        return

    updated = await _refresh_profile_screen_in_place(source_message, state, app_user, status_text)
    if updated:
        return
    await _show_profile_screen(source_message, state, app_user, status_text=status_text)


async def _refresh_profile_screen_in_place(
    source_message: Message,
    state: FSMContext,
    app_user: User,
    status_text: str,
) -> bool:
    data = await state.get_data()
    card_message_id = data.get(PROFILE_CARD_MESSAGE_ID_KEY)
    editor_message_id = data.get(PROFILE_EDITOR_MESSAGE_ID_KEY)
    if not isinstance(card_message_id, int) or not isinstance(editor_message_id, int):
        return False

    try:
        await source_message.bot.edit_message_text(
            chat_id=source_message.chat.id,
            message_id=card_message_id,
            text=_profile_summary(app_user),
            reply_markup=None,
        )
        await source_message.bot.edit_message_text(
            chat_id=source_message.chat.id,
            message_id=editor_message_id,
            text=_profile_editor_panel_text(status_text),
            reply_markup=profile_edit_keyboard(app_user.telegram_id),
        )
    except TelegramBadRequest:
        return False

    await state.set_state(None)
    await state.update_data(**{PROFILE_INTERESTS_KEY: list(app_user.interests_json)})
    return True


async def _edit_profile_editor_panel(
    source_message: Message | None,
    state: FSMContext,
    app_user: User,
    text: str,
    *,
    reply_markup: object | None = None,
) -> bool:
    if source_message is None:
        return False

    data = await state.get_data()
    editor_message_id = data.get(PROFILE_EDITOR_MESSAGE_ID_KEY)
    if not isinstance(editor_message_id, int):
        await _show_profile_screen(source_message, state, app_user)
        return False

    try:
        await source_message.bot.edit_message_text(
            chat_id=source_message.chat.id,
            message_id=editor_message_id,
            text=text,
            reply_markup=reply_markup,
        )
    except TelegramBadRequest:
        await _show_profile_screen(source_message, state, app_user)
        return False
    return True


async def _delete_tracked_profile_messages(bot, chat_id: int, state: FSMContext) -> None:
    data = await state.get_data()
    message_ids = {
        data.get(PROFILE_CARD_MESSAGE_ID_KEY),
        data.get(PROFILE_EDITOR_MESSAGE_ID_KEY),
    }
    for message_id in message_ids:
        if not isinstance(message_id, int):
            continue
        try:
            await bot.delete_message(chat_id=chat_id, message_id=message_id)
        except TelegramBadRequest:
            pass


async def _delete_message(message: Message) -> None:
    try:
        await message.delete()
    except TelegramBadRequest:
        pass


def _profile_editor_panel_text(status_text: str | None = None) -> str:
    if not status_text:
        return PROFILE_EDITOR_HEADING_TEXT
    return f"{status_text}\n\n{PROFILE_EDITOR_HEADING_TEXT}"


def _profile_prompt_text(prompt_text: str, *, error_text: str | None = None) -> str:
    if not error_text:
        return prompt_text
    return f"\u274c {error_text}\n\n{prompt_text}"


def _profile_summary(user: User) -> str:
    premium_status = "Active" if user.has_active_vip() else "Locked"
    return (
        "\U0001f464 Your Profile\n\n"
        f"{PROFILE_SEPARATOR}\n\n"
        f"\U0001f3ad Nickname: {user.nickname or 'Add a nickname \u270f\ufe0f'}\n"
        f"\U0001f382 Age: {user.age or 'Not set'}\n"
        f"\U0001f9d1 Gender: {user.gender.value.title() if user.gender else 'Not set'}\n\n"
        f"\U0001f3af Match Preference: {format_preferred_gender(user.preferred_gender)}\n"
        f"\u2728 Interests: {format_interests(user.interests_json)}\n\n"
        f"\U0001f48e Premium: {premium_status}\n\n"
        f"{PROFILE_SEPARATOR}"
    )
