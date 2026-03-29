from __future__ import annotations

from collections.abc import Iterable
from typing import Protocol

from aiogram.types import InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from app.utils.text import BUY_POINTS_BUTTON_TEXT, FREE_BUTTON_TEXT


class PackageLike(Protocol):
    code: str
    button_label: str


def points_wallet_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text=BUY_POINTS_BUTTON_TEXT, callback_data="payments:open")
    builder.button(text=FREE_BUTTON_TEXT, callback_data="payments:free")
    builder.adjust(2)
    return builder.as_markup()


def points_package_keyboard(packages: Iterable[PackageLike]) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for package in packages:
        builder.button(
            text=package.button_label,
            callback_data=f"payments:package:{package.code}",
        )
    builder.adjust(2, 1)
    return builder.as_markup()
