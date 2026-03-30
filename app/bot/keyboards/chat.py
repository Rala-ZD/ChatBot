from __future__ import annotations

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, KeyboardButton, ReplyKeyboardMarkup


def active_chat_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="Next"), KeyboardButton(text="End")],
            [KeyboardButton(text="Report")],
        ],
        resize_keyboard=True,
    )


def chat_summary_keyboard(session_id: int, *, allow_rating: bool = True) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    if allow_rating:
        rows.append(
            [
                InlineKeyboardButton(text="\U0001f44d", callback_data=f"chatrate:good:{session_id}"),
                InlineKeyboardButton(text="\U0001f44e", callback_data=f"chatrate:bad:{session_id}"),
            ]
        )
    rows.append(
        [
            InlineKeyboardButton(text="\U0001f6a9", callback_data=f"chatrate:report:{session_id}"),
        ]
    )
    return InlineKeyboardMarkup(inline_keyboard=rows)
