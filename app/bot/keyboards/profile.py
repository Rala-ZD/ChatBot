from __future__ import annotations

from aiogram.types import InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder


def profile_edit_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="Age", callback_data="profile:edit:age")
    builder.button(text="Gender", callback_data="profile:edit:gender")
    builder.button(text="Nickname", callback_data="profile:edit:nickname")
    builder.button(text="Filter", callback_data="profile:edit:preferred_gender")
    builder.button(text="Interests", callback_data="profile:edit:interests")
    builder.adjust(2, 2, 1)
    return builder.as_markup()
