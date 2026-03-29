from __future__ import annotations

from aiogram.types import InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from app.utils.enums import Gender, PreferredGender


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
