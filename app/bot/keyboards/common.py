from __future__ import annotations

from aiogram.types import InlineKeyboardMarkup, KeyboardButton, ReplyKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from app.utils.text import SEARCH_CANCEL_BUTTON_TEXT, SELECT_GENDER_BUTTON_TEXT


def main_menu_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="Start Chat"), KeyboardButton(text="Profile")],
            [KeyboardButton(text=SELECT_GENDER_BUTTON_TEXT)],
            [KeyboardButton(text="Safety"), KeyboardButton(text="Help")],
        ],
        resize_keyboard=True,
    )


def searching_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=SEARCH_CANCEL_BUTTON_TEXT)],
        ],
        resize_keyboard=True,
    )


def rules_accept_keyboard(owner_telegram_id: int | None = None) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    callback_data = "register:consent"
    if owner_telegram_id is not None:
        callback_data = f"{callback_data}:{owner_telegram_id}"
    builder.button(text="Continue", callback_data=callback_data)
    return builder.as_markup()


def confirm_keyboard(confirm_data: str, edit_data: str) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="Save", callback_data=confirm_data)
    builder.button(text="Edit", callback_data=edit_data)
    builder.adjust(2)
    return builder.as_markup()
