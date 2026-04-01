from __future__ import annotations

from collections.abc import Collection

from aiogram.types import InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from app.utils.enums import Gender, PreferredGender

REGISTRATION_REGION_OPTIONS: tuple[tuple[str, str], ...] = (
    ("global", "🌍 Global (English)"),
    ("india", "🇮🇳 India"),
    ("sri_lanka", "🇱🇰 Sri Lanka"),
    ("brazil", "🇧🇷 Brazil"),
    ("spanish", "🇪🇸 Spanish"),
    ("arabic", "🇸🇦 Arabic"),
    ("indonesia", "🇮🇩 Indonesia"),
    ("philippines", "🇵🇭 Philippines"),
    ("russia", "🇷🇺 Russia"),
)

REGISTRATION_AGE_OPTIONS: tuple[tuple[str, str], ...] = (
    ("under18", "Under 18 years old"),
    ("18_21", "From 18 to 21 years old"),
    ("22_25", "From 22 to 25 years old"),
    ("26_45", "From 26 to 45 years old"),
)

REGISTRATION_INTEREST_OPTIONS: tuple[tuple[str, str], ...] = (
    ("communication", "Communication"),
    ("flirt", "Flirt"),
    ("memes", "Memes"),
    ("games", "Games"),
    ("loneliness", "Loneliness"),
    ("journeys", "Journeys"),
    ("music", "Music"),
    ("painting", "Painting"),
    ("anime", "Anime"),
    ("films", "Films"),
    ("animals", "Animals"),
    ("books", "Books"),
    ("sport", "Sport"),
    ("news", "News"),
)


def _owned_callback_data(base: str, owner_telegram_id: int | None) -> str:
    if owner_telegram_id is None:
        return base
    return f"{base}:{owner_telegram_id}"


def age_keyboard(
    prefix: str = "register:age",
    *,
    owner_telegram_id: int | None = None,
) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for slug, label in REGISTRATION_AGE_OPTIONS:
        builder.button(
            text=label,
            callback_data=_owned_callback_data(f"{prefix}:{slug}", owner_telegram_id),
        )
    builder.adjust(2)
    return builder.as_markup()


def gender_keyboard(
    prefix: str = "register:gender",
    *,
    owner_telegram_id: int | None = None,
) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for gender in Gender:
        builder.button(
            text=gender.value.title(),
            callback_data=_owned_callback_data(f"{prefix}:{gender.value}", owner_telegram_id),
        )
    builder.adjust(2)
    return builder.as_markup()


def preferred_gender_keyboard(prefix: str = "register:preferred") -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="Anyone", callback_data=f"{prefix}:{PreferredGender.ANY.value}")
    for gender in Gender:
        builder.button(text=gender.value.title(), callback_data=f"{prefix}:{gender.value}")
    builder.adjust(2)
    return builder.as_markup()


def skip_keyboard(callback_data: str) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="Skip", callback_data=callback_data)
    return builder.as_markup()


def region_keyboard(
    prefix: str = "register:region",
    *,
    owner_telegram_id: int | None = None,
) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for slug, label in REGISTRATION_REGION_OPTIONS:
        builder.button(
            text=label,
            callback_data=_owned_callback_data(f"{prefix}:{slug}", owner_telegram_id),
        )
    builder.button(
        text="↩️ Back",
        callback_data=_owned_callback_data(f"{prefix}:back", owner_telegram_id),
    )
    builder.adjust(2, 2, 2, 2, 1, 1)
    return builder.as_markup()


def interests_keyboard(
    selected: Collection[str] | None = None,
    *,
    owner_telegram_id: int | None = None,
) -> InlineKeyboardMarkup:
    selected_set = set(selected or ())
    builder = InlineKeyboardBuilder()
    for slug, label in REGISTRATION_INTEREST_OPTIONS:
        prefix = "✅ " if slug in selected_set else ""
        builder.button(
            text=f"{prefix}{label}",
            callback_data=_owned_callback_data(f"register:interest:toggle:{slug}", owner_telegram_id),
        )
    builder.button(
        text="Skip",
        callback_data=_owned_callback_data("register:interest:skip", owner_telegram_id),
    )
    builder.button(
        text="Done",
        callback_data=_owned_callback_data("register:interest:done", owner_telegram_id),
    )
    builder.adjust(*([2] * ((len(REGISTRATION_INTEREST_OPTIONS) // 2) + 1)))
    return builder.as_markup()
