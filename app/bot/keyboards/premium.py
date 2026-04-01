from __future__ import annotations

from aiogram.types import InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

def premium_gender_gate_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="\U0001f389 Get Free VIP", callback_data="selectgender:free")
    builder.button(text="\u21a9\ufe0f Back", callback_data="selectgender:back")
    builder.adjust(1, 1)
    return builder.as_markup()


def premium_gender_referral_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(
        text="\u2728 Exchange 3 Points for 6 Hours",
        callback_data="selectgender:referral:exchange",
    )
    builder.button(text="\u21a9\ufe0f Back", callback_data="selectgender:referral:back")
    builder.adjust(1, 1)
    return builder.as_markup()


def premium_points_exchange_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(
        text="\u2728 Exchange 3 Points for 6 Hours",
        callback_data="referral:exchange",
    )
    return builder.as_markup()
