from __future__ import annotations

from collections.abc import Collection

from aiogram.types import InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from app.utils.enums import Gender, PreferredGender

REGISTRATION_INTEREST_OPTIONS: tuple[tuple[str, str], ...] = (
    ("communication", "Communication"),
    ("flirt", "Flirt"),
    ("memes", "Memes"),
    ("games", "Games"),
    ("loneliness", "Loneliness"),
    ("journeys", "Journeys"),
    ("music", "Music"),
    ("painting", "Painting"),
    ("anime", "Anime"),
    ("films", "Films"),
    ("animals", "Animals"),
    ("books", "Books"),
    ("sport", "Sport"),
    ("news", "News"),
)


def gender_keyboard(prefix: str = "register:gender") -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for gender in Gender:
        builder.button(text=gender.value.title(), callback_data=f"{prefix}:{gender.value}")
    builder.adjust(2)
    return builder.as_markup()


def preferred_gender_keyboard(prefix: str = "register:preferred") -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="Anyone", callback_data=f"{prefix}:{PreferredGender.ANY.value}")
    for gender in Gender:
        builder.button(text=gender.value.title(), callback_data=f"{prefix}:{gender.value}")
    builder.adjust(2)
    return builder.as_markup()


def skip_keyboard(callback_data: str) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="Skip", callback_data=callback_data)
    return builder.as_markup()


def interests_keyboard(selected: Collection[str] | None = None) -> InlineKeyboardMarkup:
    selected_set = set(selected or ())
    builder = InlineKeyboardBuilder()
    for slug, label in REGISTRATION_INTEREST_OPTIONS:
        prefix = "✅ " if slug in selected_set else ""
        builder.button(
            text=f"{prefix}{label}",
            callback_data=f"register:interest:toggle:{slug}",
        )
    builder.button(text="Skip", callback_data="register:interest:skip")
    builder.button(text="Done", callback_data="register:interest:done")
    builder.adjust(*([2] * ((len(REGISTRATION_INTEREST_OPTIONS) // 2) + 1)))
    return builder.as_markup()
