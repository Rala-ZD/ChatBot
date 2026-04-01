from __future__ import annotations

from dataclasses import dataclass, field
from datetime import timedelta
from types import SimpleNamespace

import pytest

from app.bot.handlers.select_gender import (
    close_select_gender_gate,
    exchange_points_for_select_gender_premium,
    handle_legacy_referral_wallet_callback,
    open_select_gender,
    open_select_gender_referral,
    preview_vip_plan,
    return_to_select_gender_gate,
)
from app.bot.keyboards.chat import active_chat_keyboard
from app.bot.keyboards.common import main_menu_keyboard
from app.bot.keyboards.payments import points_package_keyboard, points_wallet_keyboard
from app.bot.keyboards.premium import (
    premium_gender_gate_keyboard,
    premium_gender_referral_keyboard,
)
from app.bot.keyboards.profile import profile_edit_keyboard
from app.services.exceptions import ValidationError
from app.services.payment_service import PointsPackage
from app.utils.text import (
    BUY_POINTS_BUTTON_TEXT,
    FREE_BUTTON_TEXT,
    INVITE_UNAVAILABLE_TEXT,
    RETURNING_HOME_TEXT,
    SEARCHING_TEXT,
    SELECT_GENDER_BUTTON_TEXT,
    build_gender_selection_text,
    build_match_found_text,
    build_premium_gender_gate_text,
    build_referral_premium_text,
)
from app.utils.time import utcnow
from tests.conftest import build_user


def _reply_keyboard_texts(markup) -> list[str]:
    if markup is None:
        return []
    return [button.text for row in markup.keyboard for button in row]


def _inline_keyboard_texts(markup) -> list[str]:
    if markup is None:
        return []
    return [button.text for row in markup.inline_keyboard for button in row]


class FakeUserService:
    def __init__(self, *, referral_count: int = 0) -> None:
        self.referral_count = referral_count

    def ensure_registered(self, _user) -> None:
        return None

    async def count_registered_referrals(self, _user) -> int:
        return self.referral_count

    async def purchase_vip(self, user):
        if user.points_balance < 3:
            raise ValidationError("Need 3 points to unlock 6 hours of premium")
        user.points_balance -= 3
        now = utcnow()
        vip_start = user.vip_until if user.vip_until and user.vip_until > now else now
        user.vip_until = vip_start + timedelta(hours=6)
        return user

    async def update_profile(self, user, **updates):
        for field, value in updates.items():
            setattr(user, field, value)
        return user


class FakeBot:
    def __init__(self, username: str | None = "testbot") -> None:
        self.username = username

    async def get_me(self):
        return SimpleNamespace(username=self.username)


@dataclass
class FakeMessage:
    bot: FakeBot
    answers: list[dict[str, object | None]] = field(default_factory=list)
    edits: list[dict[str, object | None]] = field(default_factory=list)

    async def answer(self, text: str, reply_markup=None, **_: object) -> None:
        self.answers.append({"text": text, "reply_markup": reply_markup})

    async def edit_text(self, text: str, reply_markup=None, **_: object) -> None:
        self.edits.append({"text": text, "reply_markup": reply_markup})


@dataclass
class FakeCallbackQuery:
    data: str
    message: FakeMessage | None
    answered: list[dict[str, object | None]] = field(default_factory=list)

    async def answer(self, text: str | None = None, show_alert: bool = False) -> None:
        self.answered.append({"text": text, "show_alert": show_alert})


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


def test_premium_gate_keyboard_has_only_free_vip_and_back() -> None:
    keyboard = premium_gender_gate_keyboard()
    texts = _inline_keyboard_texts(keyboard)

    assert texts == ["🎉 Get Free VIP", "↩️ Back"]
    assert BUY_POINTS_BUTTON_TEXT not in texts
    assert FREE_BUTTON_TEXT not in texts
    assert "💎 1 Week" not in texts
    assert "💎 1 Month" not in texts
    assert "💎 6 Months" not in texts


def test_premium_referral_keyboard_has_exchange_and_back() -> None:
    keyboard = premium_gender_referral_keyboard()
    texts = _inline_keyboard_texts(keyboard)

    assert texts == ["✨ Exchange 3 Points for 6 Hours", "↩️ Back"]
    assert "Points Wallet" not in texts
    assert "Referral TOP" not in texts


def test_points_wallet_keyboard_still_exists_elsewhere() -> None:
    keyboard = points_wallet_keyboard()
    texts = _inline_keyboard_texts(keyboard)
    assert texts == [BUY_POINTS_BUTTON_TEXT, FREE_BUTTON_TEXT]


def test_points_package_keyboard_has_expected_packs() -> None:
    keyboard = points_package_keyboard(
        (
            PointsPackage(code="points_10", points_amount=10, stars_amount=25),
            PointsPackage(code="points_50", points_amount=50, stars_amount=100),
            PointsPackage(code="points_150", points_amount=150, stars_amount=250),
        )
    )
    texts = _inline_keyboard_texts(keyboard)
    assert texts == ["10 pts", "50 pts", "150 pts"]


def test_profile_keyboard_is_balanced_for_mobile() -> None:
    keyboard = profile_edit_keyboard()
    texts = _inline_keyboard_texts(keyboard)
    assert texts == ["Age", "Gender", "Nickname", "Filter", "Interests"]
    assert [len(row) for row in keyboard.inline_keyboard] == [2, 2, 1]


def test_premium_gate_text_uses_referral_only_copy() -> None:
    text = build_premium_gender_gate_text()

    assert text == (
        "💎 Premium Matching\n\n"
        "Invite 3 friends to unlock 6 hours of premium.\n\n"
        "🎯 Search by gender\n"
        "✨ Better matching"
    )
    assert "Buy Points" not in text
    assert "No ads" not in text


def test_referral_premium_text_shows_points_count_rules_and_link() -> None:
    text = build_referral_premium_text("testbot", "REFCODE1", 2, 1)

    assert text == (
        "🎉 Get Free VIP\n\n"
        "Invite friends and earn premium points.\n\n"
        "💎 Your points: 2\n"
        "👥 Joined by your link: 1\n\n"
        "1 friend = 1 point\n"
        "3 points = 6 hours premium\n\n"
        "Your link\n"
        "https://t.me/testbot?start=ref_REFCODE1"
    )
    assert "Referral TOP" not in text
    assert "Points Wallet" not in text


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
    assert text == (
        "🎉 You’ve got a match!\n\n"
        "👤 Stranger\n"
        "✨ Interests: Games, Night Chats\n"
        "⭐ Rating: 5.0\n\n"
        "💬 Say hi and break the ice 😉\n"
        "👇 Tap below to control your chat"
    )


@pytest.mark.asyncio
async def test_non_vip_select_gender_entry_shows_referral_only_gate() -> None:
    message = FakeMessage(bot=FakeBot())
    app_user = build_user(1, points_balance=2)

    await open_select_gender(message, app_user, FakeUserService())

    assert message.answers[-1]["text"] == build_premium_gender_gate_text()
    assert _inline_keyboard_texts(message.answers[-1]["reply_markup"]) == [
        "🎉 Get Free VIP",
        "↩️ Back",
    ]


@pytest.mark.asyncio
async def test_active_vip_select_gender_entry_still_shows_gender_picker() -> None:
    message = FakeMessage(bot=FakeBot())
    app_user = build_user(1, vip_active=True)

    await open_select_gender(message, app_user, FakeUserService())

    assert "Premium Active" in str(message.answers[-1]["text"])
    assert _inline_keyboard_texts(message.answers[-1]["reply_markup"]) == [
        "Anyone",
        "Male",
        "Female",
        "Other",
    ]


@pytest.mark.asyncio
async def test_legacy_plan_callback_returns_to_referral_only_gate() -> None:
    callback = FakeCallbackQuery(
        data="selectgender:plan:week",
        message=FakeMessage(bot=FakeBot()),
    )

    await preview_vip_plan(callback, build_user(1), FakeUserService())

    assert callback.message.edits == [
        {
            "text": build_premium_gender_gate_text(),
            "reply_markup": premium_gender_gate_keyboard(),
        }
    ]
    assert callback.answered == [
        {
            "text": "Invite 3 friends to unlock 6 hours of premium",
            "show_alert": True,
        }
    ]


@pytest.mark.asyncio
async def test_get_free_vip_opens_referral_screen() -> None:
    callback = FakeCallbackQuery(
        data="selectgender:free",
        message=FakeMessage(bot=FakeBot("mybot")),
    )
    app_user = build_user(1, referral_code="FREEVIP42", points_balance=2)

    await open_select_gender_referral(
        callback,
        app_user,
        FakeUserService(referral_count=1),
    )

    assert callback.answered == [{"text": None, "show_alert": False}]
    assert callback.message.edits == [
        {
            "text": build_referral_premium_text("mybot", "FREEVIP42", 2, 1),
            "reply_markup": premium_gender_referral_keyboard(),
        }
    ]


@pytest.mark.asyncio
async def test_get_free_vip_handles_missing_bot_username() -> None:
    callback = FakeCallbackQuery(
        data="selectgender:free",
        message=FakeMessage(bot=FakeBot(None)),
    )

    await open_select_gender_referral(callback, build_user(1), FakeUserService())

    assert callback.answered == [{"text": INVITE_UNAVAILABLE_TEXT, "show_alert": True}]
    assert callback.message.edits == []


@pytest.mark.asyncio
async def test_exchange_points_for_premium_succeeds_and_opens_gender_selection() -> None:
    callback = FakeCallbackQuery(
        data="selectgender:referral:exchange",
        message=FakeMessage(bot=FakeBot()),
    )
    app_user = build_user(1, points_balance=3)

    await exchange_points_for_select_gender_premium(callback, app_user, FakeUserService())

    assert callback.answered == [{"text": None, "show_alert": False}]
    assert app_user.points_balance == 0
    assert callback.message.edits == [
        {
            "text": build_gender_selection_text(
                app_user.preferred_gender,
                app_user.vip_until,
                success=True,
            ),
            "reply_markup": callback.message.edits[0]["reply_markup"],
        }
    ]
    assert _inline_keyboard_texts(callback.message.edits[0]["reply_markup"]) == [
        "Anyone",
        "Male",
        "Female",
        "Other",
    ]


@pytest.mark.asyncio
async def test_exchange_points_for_premium_rejects_low_balance() -> None:
    callback = FakeCallbackQuery(
        data="selectgender:referral:exchange",
        message=FakeMessage(bot=FakeBot()),
    )
    app_user = build_user(1, points_balance=2)

    await exchange_points_for_select_gender_premium(callback, app_user, FakeUserService())

    assert callback.answered == [
        {"text": "Need 3 points to unlock 6 hours of premium", "show_alert": True}
    ]
    assert callback.message.edits == []


@pytest.mark.asyncio
async def test_legacy_wallet_callback_reopens_new_referral_screen() -> None:
    callback = FakeCallbackQuery(
        data="selectgender:referral:wallet",
        message=FakeMessage(bot=FakeBot("mybot")),
    )
    app_user = build_user(1, referral_code="FREEVIP42", points_balance=5)

    await handle_legacy_referral_wallet_callback(
        callback,
        app_user,
        FakeUserService(referral_count=3),
    )

    assert callback.message.edits == [
        {
            "text": build_referral_premium_text("mybot", "FREEVIP42", 5, 3),
            "reply_markup": premium_gender_referral_keyboard(),
        }
    ]
    assert callback.answered == [
        {"text": "Use referrals to earn premium now", "show_alert": True}
    ]


@pytest.mark.asyncio
async def test_referral_screen_back_returns_to_premium_gate() -> None:
    callback = FakeCallbackQuery(
        data="selectgender:referral:back",
        message=FakeMessage(bot=FakeBot()),
    )

    await return_to_select_gender_gate(callback, build_user(1), FakeUserService())

    assert callback.answered == [{"text": None, "show_alert": False}]
    assert callback.message.edits == [
        {
            "text": build_premium_gender_gate_text(),
            "reply_markup": premium_gender_gate_keyboard(),
        }
    ]


@pytest.mark.asyncio
async def test_premium_gate_back_returns_to_home_copy() -> None:
    callback = FakeCallbackQuery(
        data="selectgender:back",
        message=FakeMessage(bot=FakeBot()),
    )

    await close_select_gender_gate(callback, build_user(1), FakeUserService())

    assert callback.answered == [{"text": None, "show_alert": False}]
    assert callback.message.edits == [{"text": RETURNING_HOME_TEXT, "reply_markup": None}]


def test_select_gender_flow_keeps_main_menu_layout_intact() -> None:
    texts = _reply_keyboard_texts(main_menu_keyboard())
    assert texts == ["Start Chat", "Profile", SELECT_GENDER_BUTTON_TEXT, "Safety", "Help"]
