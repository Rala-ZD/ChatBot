from __future__ import annotations

from aiogram.types import KeyboardButton, ReplyKeyboardMarkup


def active_chat_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="Next"), KeyboardButton(text="End")],
            [KeyboardButton(text="Report")],
        ],
        resize_keyboard=True,
    )
