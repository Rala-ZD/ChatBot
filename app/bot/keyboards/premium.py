from __future__ import annotations

from aiogram.types import InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from app.utils.text import BUY_POINTS_BUTTON_TEXT, FREE_BUTTON_TEXT


def premium_gender_gate_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="Unlock", callback_data="selectgender:unlock")
    builder.button(text=FREE_BUTTON_TEXT, callback_data="payments:free")
    builder.button(text=BUY_POINTS_BUTTON_TEXT, callback_data="payments:open")
    builder.adjust(1, 2)
    return builder.as_markup()
