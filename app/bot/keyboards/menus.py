from __future__ import annotations

from aiogram.types import InlineKeyboardMarkup, KeyboardButton, ReplyKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from app.bot.keyboards.callbacks import ProfileCallback, RegistrationCallback, ReportCallback
from app.db.models import Gender, PreferredGender, ReportReason
from app.utils.constants import (
    CHAT_MENU_END,
    CHAT_MENU_NEXT,
    CHAT_MENU_REPORT,
    MAIN_MENU_EDIT_PROFILE,
    MAIN_MENU_HELP,
    MAIN_MENU_RULES,
    MAIN_MENU_START_CHAT,
    WAITING_MENU_CANCEL,
)


def main_menu_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=MAIN_MENU_START_CHAT), KeyboardButton(text=MAIN_MENU_EDIT_PROFILE)],
            [KeyboardButton(text=MAIN_MENU_RULES), KeyboardButton(text=MAIN_MENU_HELP)],
        ],
        resize_keyboard=True,
    )


def waiting_menu_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text=WAITING_MENU_CANCEL)]],
        resize_keyboard=True,
    )


def chat_menu_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=CHAT_MENU_NEXT), KeyboardButton(text=CHAT_MENU_END)],
            [KeyboardButton(text=CHAT_MENU_REPORT)],
        ],
        resize_keyboard=True,
    )


def registration_start_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(
        text="Continue Registration",
        callback_data=RegistrationCallback(action="begin"),
    )
    return builder.as_markup()


def gender_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for gender in Gender:
        builder.button(
            text=gender.value.replace("_", " ").title(),
            callback_data=RegistrationCallback(action="gender", value=gender.value),
        )
    builder.adjust(2)
    return builder.as_markup()


def preferred_gender_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(
        text="Any",
        callback_data=RegistrationCallback(action="preferred_gender", value=PreferredGender.ANY.value),
    )
    for gender in Gender:
        builder.button(
            text=gender.value.replace("_", " ").title(),
            callback_data=RegistrationCallback(action="preferred_gender", value=gender.value),
        )
    builder.button(
        text="Skip",
        callback_data=RegistrationCallback(action="preferred_gender", value="skip"),
    )
    builder.adjust(2)
    return builder.as_markup()


def skip_keyboard(action: str = "skip") -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(
        text="Skip",
        callback_data=RegistrationCallback(action=action, value="skip"),
    )
    return builder.as_markup()


def consent_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(
        text="I Agree",
        callback_data=RegistrationCallback(action="consent", value="accept"),
    )
    return builder.as_markup()


def profile_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for field, label in [
        ("age", "Edit Age"),
        ("gender", "Edit Gender"),
        ("nickname", "Edit Nickname"),
        ("preferred_gender", "Edit Preferred Gender"),
        ("interests_json", "Edit Interests"),
    ]:
        builder.button(text=label, callback_data=ProfileCallback(field=field))
    builder.adjust(1)
    return builder.as_markup()


def report_reasons_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for reason in ReportReason:
        builder.button(
            text=reason.value.replace("_", " ").title(),
            callback_data=ReportCallback(action="reason", value=reason.value),
        )
    builder.adjust(2)
    return builder.as_markup()


def report_note_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(
        text="Skip Note",
        callback_data=ReportCallback(action="note", value="skip"),
    )
    return builder.as_markup()
