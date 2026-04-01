from __future__ import annotations

from aiogram.types import InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder


def premium_gender_gate_keyboard(owner_telegram_id: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(
        text="\U0001f48e 1 Week",
        callback_data=f"selectgender:plan:week:{owner_telegram_id}",
    )
    builder.button(
        text="\U0001f48e 1 Month",
        callback_data=f"selectgender:plan:month:{owner_telegram_id}",
    )
    builder.button(
        text="\U0001f48e 6 Months",
        callback_data=f"selectgender:plan:6months:{owner_telegram_id}",
    )
    builder.button(text="\U0001f389 Get Free VIP", callback_data=f"selectgender:free:{owner_telegram_id}")
    builder.button(text="\u21a9\ufe0f Back", callback_data=f"selectgender:back:{owner_telegram_id}")
    builder.adjust(1, 1, 1, 1, 1)
    return builder.as_markup()


def premium_gender_referral_keyboard(owner_telegram_id: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(
        text="\u2728 Exchange 3 Points for 6 Hours",
        callback_data=f"selectgender:referral:exchange:{owner_telegram_id}",
    )
    builder.button(text="\u21a9\ufe0f Back", callback_data=f"selectgender:referral:back:{owner_telegram_id}")
    builder.adjust(1, 1)
    return builder.as_markup()


def premium_points_exchange_keyboard(owner_telegram_id: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(
        text="\u2728 Exchange 3 Points for 6 Hours",
        callback_data=f"referral:exchange:{owner_telegram_id}",
    )
    return builder.as_markup()
