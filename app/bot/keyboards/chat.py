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


def chat_summary_keyboard(session_id: int) -> InlineKeyboardMarkup:
    rows = [
        [
            InlineKeyboardButton(text="\U0001f60d Great", callback_data=f"chatrate:great:{session_id}"),
            InlineKeyboardButton(text="\U0001f642 Okay", callback_data=f"chatrate:okay:{session_id}"),
        ],
        [
            InlineKeyboardButton(text="\U0001f621 Bad", callback_data=f"chatrate:bad:{session_id}"),
            InlineKeyboardButton(text="\U0001f6ab Spam / Ads", callback_data=f"chatrate:spam:{session_id}"),
        ],
    ]
    return InlineKeyboardMarkup(inline_keyboard=rows)
