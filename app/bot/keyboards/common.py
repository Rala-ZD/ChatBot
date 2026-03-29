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


def rules_accept_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="Continue", callback_data="register:consent")
    return builder.as_markup()


def confirm_keyboard(confirm_data: str, edit_data: str) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="Save", callback_data=confirm_data)
    builder.button(text="Edit", callback_data=edit_data)
    builder.adjust(2)
    return builder.as_markup()
