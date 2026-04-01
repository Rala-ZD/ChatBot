from __future__ import annotations

from collections.abc import Collection

from aiogram.types import InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from app.bot.keyboards.registration import REGISTRATION_INTEREST_OPTIONS
from app.utils.enums import Gender, PreferredGender


def _owned_callback_data(base: str, owner_telegram_id: int) -> str:
    return f"{base}:{owner_telegram_id}"


def profile_edit_keyboard(owner_telegram_id: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(
        text="\U0001f9d1 Nickname",
        callback_data=_owned_callback_data("profile:edit:nickname", owner_telegram_id),
    )
    builder.button(
        text="\U0001f382 Age",
        callback_data=_owned_callback_data("profile:edit:age", owner_telegram_id),
    )
    builder.button(
        text="\U0001f6b9 Gender",
        callback_data=_owned_callback_data("profile:edit:gender", owner_telegram_id),
    )
    builder.button(
        text="\U0001f3af Filter",
        callback_data=_owned_callback_data("profile:edit:preferred_gender", owner_telegram_id),
    )
    builder.button(
        text="\u2728 Interests",
        callback_data=_owned_callback_data("profile:edit:interests", owner_telegram_id),
    )
    builder.adjust(2, 2, 1)
    return builder.as_markup()


def profile_gender_keyboard(owner_telegram_id: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for gender in Gender:
        builder.button(
            text=gender.value.title(),
            callback_data=_owned_callback_data(f"profile:gender:{gender.value}", owner_telegram_id),
        )
    builder.adjust(2)
    return builder.as_markup()


def profile_filter_keyboard(owner_telegram_id: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(
        text="Anyone",
        callback_data=_owned_callback_data(f"profile:preferred:{PreferredGender.ANY.value}", owner_telegram_id),
    )
    for gender in Gender:
        builder.button(
            text=gender.value.title(),
            callback_data=_owned_callback_data(f"profile:preferred:{gender.value}", owner_telegram_id),
        )
    builder.adjust(2, 2)
    return builder.as_markup()


def profile_interests_keyboard(
    selected: Collection[str] | None = None,
    *,
    owner_telegram_id: int,
) -> InlineKeyboardMarkup:
    selected_set = set(selected or ())
    builder = InlineKeyboardBuilder()
    for slug, label in REGISTRATION_INTEREST_OPTIONS:
        prefix = "\u2705 " if slug in selected_set else ""
        builder.button(
            text=f"{prefix}{label}",
            callback_data=_owned_callback_data(f"profile:interest:toggle:{slug}", owner_telegram_id),
        )
    builder.button(
        text="Done",
        callback_data=_owned_callback_data("profile:interest:done", owner_telegram_id),
    )
    builder.adjust(*([2] * (len(REGISTRATION_INTEREST_OPTIONS) // 2)), 1)
    return builder.as_markup()
