from __future__ import annotations

from datetime import timedelta

from app.bot.keyboards.chat import active_chat_keyboard
from app.bot.keyboards.common import main_menu_keyboard
from app.bot.keyboards.payments import points_package_keyboard, points_wallet_keyboard
from app.bot.keyboards.premium import premium_gender_gate_keyboard
from app.bot.keyboards.profile import profile_edit_keyboard
from app.services.payment_service import PointsPackage
from app.utils.text import (
    BUY_POINTS_BUTTON_TEXT,
    FREE_BUTTON_TEXT,
    SEARCHING_TEXT,
    SELECT_GENDER_BUTTON_TEXT,
    build_gender_selection_text,
    build_match_found_text,
    build_points_status_text,
    build_premium_gender_gate_text,
)
from app.utils.time import utcnow


def test_main_menu_contains_select_gender_button() -> None:
    keyboard = main_menu_keyboard()
    texts = [button.text for row in keyboard.keyboard for button in row]
    assert SELECT_GENDER_BUTTON_TEXT in texts
    assert "Profile" in texts
    assert "Safety" in texts


def test_active_chat_keyboard_is_short_and_balanced() -> None:
    keyboard = active_chat_keyboard()
    texts = [button.text for row in keyboard.keyboard for button in row]
    assert texts == ["Next", "End", "Report"]


def test_premium_gate_keyboard_has_required_buttons() -> None:
    keyboard = premium_gender_gate_keyboard()
    texts = [button.text for row in keyboard.inline_keyboard for button in row]
    assert texts == ["Unlock", FREE_BUTTON_TEXT, BUY_POINTS_BUTTON_TEXT]


def test_points_wallet_keyboard_has_buy_and_free_actions() -> None:
    keyboard = points_wallet_keyboard()
    texts = [button.text for row in keyboard.inline_keyboard for button in row]
    assert texts == [BUY_POINTS_BUTTON_TEXT, FREE_BUTTON_TEXT]


def test_points_package_keyboard_has_expected_packs() -> None:
    keyboard = points_package_keyboard(
        (
            PointsPackage(code="points_10", points_amount=10, stars_amount=25),
            PointsPackage(code="points_50", points_amount=50, stars_amount=100),
            PointsPackage(code="points_150", points_amount=150, stars_amount=250),
        )
    )
    texts = [button.text for row in keyboard.inline_keyboard for button in row]
    assert texts == ["10 pts", "50 pts", "150 pts"]


def test_profile_keyboard_is_balanced_for_mobile() -> None:
    keyboard = profile_edit_keyboard()
    texts = [button.text for row in keyboard.inline_keyboard for button in row]
    assert texts == ["Age", "Gender", "Nickname", "Filter", "Interests"]
    assert [len(row) for row in keyboard.inline_keyboard] == [2, 2, 1]


def test_premium_gate_text_shows_balance_and_cost() -> None:
    text = build_premium_gender_gate_text(7, 10)
    assert "Select Gender" in text
    assert "Balance: 7 points" in text
    assert "Unlock: 10 points / 1 day" in text


def test_points_status_text_shows_active_access() -> None:
    text = build_points_status_text(12, utcnow() + timedelta(days=1))
    assert "Points Wallet" in text
    assert "Balance: 12 points" in text
    assert "Premium: Active until" in text
    assert "Top up with Stars or earn them free." in text


def test_gender_selection_text_shows_preference() -> None:
    text = build_gender_selection_text("female", utcnow() + timedelta(days=1), success=True)
    assert "Premium Active" in text
    assert "Filter: Female" in text


def test_search_and_match_copy_use_headlines() -> None:
    assert SEARCHING_TEXT == (
        "🔎 Finding someone for you...\n\n"
        "💡 Tip: Be friendly — first message matters 😉\n"
        "⏳ Usually takes 3–10 seconds"
    )
    text = build_match_found_text(["games", "night chats"], "5.0")
    assert text.startswith("🐶 Partner found!")
    assert "📚 Interests: Games, Night Chats" in text
    assert "🏆 Rating: 5.0" in text


def test_match_found_text_shows_numeric_rating_when_available() -> None:
    text = build_match_found_text(["anime"], "1.4")
    assert "📚 Interests: Anime" in text
    assert "🏆 Rating: 1.4" in text
