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
from app.bot.handlers.profile import _profile_summary, show_profile
from app.bot.keyboards.chat import active_chat_keyboard
from app.bot.keyboards.common import main_menu_keyboard
from app.bot.keyboards.payments import points_package_keyboard, points_wallet_keyboard
from app.bot.keyboards.premium import (
    premium_gender_gate_keyboard,
    premium_gender_referral_keyboard,
)
from app.bot.keyboards.profile import profile_edit_keyboard
from app.services.exceptions import ValidationError
from app.services.payment_service import InvoiceRequest, PointsPackage
from app.utils.text import (
    BUY_POINTS_BUTTON_TEXT,
    FREE_BUTTON_TEXT,
    INVITE_UNAVAILABLE_TEXT,
    PREMIUM_SCREEN_UNAVAILABLE_TEXT,
    RETURNING_HOME_TEXT,
    SEARCHING_TEXT,
    SELECT_GENDER_BUTTON_TEXT,
    VIP_CHECKOUT_COMING_SOON_TEXT,
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


def _inline_keyboard_callback_data(markup) -> list[str]:
    if markup is None:
        return []
    return [button.callback_data for row in markup.inline_keyboard for button in row]


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


class FakePaymentService:
    def __init__(self, *, fail: bool = False) -> None:
        self.fail = fail
        self.requested_codes: list[str] = []

    async def create_invoice_request(self, _user, plan_code: str) -> InvoiceRequest:
        self.requested_codes.append(plan_code)
        if self.fail:
            raise ValidationError("unavailable")
        return InvoiceRequest(
            title=f"{plan_code} title",
            description=f"{plan_code} description",
            payload=f"payload:{plan_code}",
            currency="XTR",
            prices=[],
            start_parameter=f"buy-{plan_code}",
        )


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
    invoices: list[dict[str, object]] = field(default_factory=list)
    next_message_id: int = 100

    def __post_init__(self) -> None:
        self.chat = SimpleNamespace(id=123)

    async def answer(self, text: str, reply_markup=None, **_: object) -> None:
        self.answers.append({"text": text, "reply_markup": reply_markup})
        self.next_message_id += 1
        return SimpleNamespace(message_id=self.next_message_id)

    async def edit_text(self, text: str, reply_markup=None, **_: object) -> None:
        self.edits.append({"text": text, "reply_markup": reply_markup})

    async def answer_invoice(self, **kwargs: object) -> None:
        self.invoices.append(kwargs)


@dataclass
class FakeCallbackQuery:
    data: str
    message: FakeMessage | None
    from_user: SimpleNamespace
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


def test_premium_gate_keyboard_has_paid_plans_free_vip_and_back() -> None:
    keyboard = premium_gender_gate_keyboard(1001)

    assert _inline_keyboard_texts(keyboard) == [
        "\U0001f48e 1 Week",
        "\U0001f48e 1 Month",
        "\U0001f48e 6 Months",
        "\U0001f389 Get Free VIP",
        "\u21a9\ufe0f Back",
    ]
    assert _inline_keyboard_callback_data(keyboard) == [
        "selectgender:plan:week:1001",
        "selectgender:plan:month:1001",
        "selectgender:plan:6months:1001",
        "selectgender:free:1001",
        "selectgender:back:1001",
    ]


def test_premium_referral_keyboard_has_exchange_and_back() -> None:
    keyboard = premium_gender_referral_keyboard(1001)

    assert _inline_keyboard_texts(keyboard) == [
        "\u2728 Exchange 3 Points for 6 Hours",
        "\u21a9\ufe0f Back",
    ]
    assert _inline_keyboard_callback_data(keyboard) == [
        "selectgender:referral:exchange:1001",
        "selectgender:referral:back:1001",
    ]
    assert "Points Wallet" not in _inline_keyboard_texts(keyboard)
    assert "Referral TOP" not in _inline_keyboard_texts(keyboard)


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
    assert _inline_keyboard_texts(keyboard) == ["10 pts", "50 pts", "150 pts"]


def test_profile_keyboard_is_balanced_for_mobile() -> None:
    keyboard = profile_edit_keyboard(1001)
    assert _inline_keyboard_texts(keyboard) == [
        "\U0001f9d1 Nickname",
        "\U0001f382 Age",
        "\U0001f6b9 Gender",
        "\U0001f3af Filter",
        "\u2728 Interests",
    ]
    assert _inline_keyboard_callback_data(keyboard) == [
        "profile:edit:nickname:1001",
        "profile:edit:age:1001",
        "profile:edit:gender:1001",
        "profile:edit:preferred_gender:1001",
        "profile:edit:interests:1001",
    ]
    assert [len(row) for row in keyboard.inline_keyboard] == [2, 2, 1]


def test_profile_summary_uses_card_layout_with_fallbacks() -> None:
    user = build_user(50, gender="female", preferred_gender="any", interests=[], vip_active=False)
    user.nickname = None

    assert _profile_summary(user) == (
        "\U0001f464 Your Profile\n\n"
        f"{'\u2500' * 16}\n\n"
        "\U0001f3ad Nickname: Add a nickname \u270f\ufe0f\n"
        "\U0001f382 Age: 25\n"
        "\U0001f9d1 Gender: Female\n\n"
        "\U0001f3af Match Preference: Anyone\n"
        "\u2728 Interests: Not set\n\n"
        "\U0001f48e Premium: Locked\n\n"
        f"{'\u2500' * 16}"
    )


def test_profile_summary_shows_active_premium_and_interests() -> None:
    user = build_user(51, gender="male", preferred_gender="female", interests=["music", "travel"], vip_active=True)
    user.nickname = "Alex"

    assert _profile_summary(user) == (
        "\U0001f464 Your Profile\n\n"
        f"{'\u2500' * 16}\n\n"
        "\U0001f3ad Nickname: Alex\n"
        "\U0001f382 Age: 25\n"
        "\U0001f9d1 Gender: Male\n\n"
        "\U0001f3af Match Preference: Female\n"
        "\u2728 Interests: music, travel\n\n"
        "\U0001f48e Premium: Active\n\n"
        f"{'\u2500' * 16}"
    )


@pytest.mark.asyncio
async def test_show_profile_uses_new_card_text_and_existing_keyboard() -> None:
    user = build_user(52, interests=["movies"], vip_active=False)
    user.nickname = "Sam"
    message = FakeMessage(bot=FakeBot())
    state = SimpleNamespace()

    async def set_state(_value):
        return None

    async def update_data(**_kwargs):
        return None

    async def get_data():
        return {}

    state.set_state = set_state
    state.update_data = update_data
    state.get_data = get_data

    await show_profile(message, state, user)

    assert [entry["text"] for entry in message.answers] == [
        "\U0001f464 Your Profile\n\n"
        f"{'\u2500' * 16}\n\n"
        "\U0001f3ad Nickname: Sam\n"
        "\U0001f382 Age: 25\n"
        "\U0001f9d1 Gender: Other\n\n"
        "\U0001f3af Match Preference: Anyone\n"
        "\u2728 Interests: movies\n\n"
        "\U0001f48e Premium: Locked\n\n"
        f"{'\u2500' * 16}",
        "\u270f\ufe0f Edit Profile",
    ]
    assert message.answers[0]["reply_markup"] is None
    assert _inline_keyboard_texts(message.answers[1]["reply_markup"]) == [
        "\U0001f9d1 Nickname",
        "\U0001f382 Age",
        "\U0001f6b9 Gender",
        "\U0001f3af Filter",
        "\u2728 Interests",
    ]


def test_premium_gate_text_uses_premium_card_copy() -> None:
    assert build_premium_gender_gate_text() == (
        "\U0001f48e Premium Matching\n\n"
        "\u2728 No ads\n"
        "\U0001f3af Search by gender\n"
        "\U0001f91d Better matching \u2022 Support the app"
    )


def test_referral_premium_text_shows_points_count_rules_and_link() -> None:
    assert build_referral_premium_text("testbot", "REFCODE1", 2, 1) == (
        "\U0001f389 Get Free VIP\n\n"
        "Invite friends and earn premium points.\n\n"
        "\U0001f48e Your points: 2\n"
        "\U0001f465 Joined by your link: 1\n\n"
        "1 friend = 1 point\n"
        "3 points = 6 hours premium\n\n"
        "Your link\n"
        "https://t.me/testbot?start=ref_REFCODE1"
    )


def test_gender_selection_text_shows_preference() -> None:
    text = build_gender_selection_text("female", utcnow() + timedelta(days=1), success=True)
    assert "Premium Active" in text
    assert "Filter: Female" in text


def test_search_and_match_copy_use_headlines() -> None:
    assert SEARCHING_TEXT == (
        "\U0001f50e Finding someone for you...\n\n"
        "\U0001f4a1 Tip: Be friendly \u2014 first message matters \U0001f609\n"
        "\u23f3 Usually takes 3\u201310 seconds"
    )
    assert build_match_found_text(["games", "night chats"], "5.0") == (
        "\U0001f389 You\u2019ve got a match!\n\n"
        "\U0001f464 Stranger\n"
        "\u2728 Interests: Games, Night Chats\n"
        "\u2b50 Rating: 5.0\n\n"
        "\U0001f4ac Say hi and break the ice \U0001f609\n"
        "\U0001f447 Tap below to control your chat"
    )


@pytest.mark.asyncio
async def test_non_vip_select_gender_entry_shows_premium_gate_with_paid_and_free_options() -> None:
    message = FakeMessage(bot=FakeBot())
    app_user = build_user(1, points_balance=2)

    await open_select_gender(message, app_user, FakeUserService())

    assert message.answers[-1]["text"] == build_premium_gender_gate_text()
    assert _inline_keyboard_texts(message.answers[-1]["reply_markup"]) == [
        "\U0001f48e 1 Week",
        "\U0001f48e 1 Month",
        "\U0001f48e 6 Months",
        "\U0001f389 Get Free VIP",
        "\u21a9\ufe0f Back",
    ]
    assert _inline_keyboard_callback_data(message.answers[-1]["reply_markup"]) == [
        f"selectgender:plan:week:{app_user.telegram_id}",
        f"selectgender:plan:month:{app_user.telegram_id}",
        f"selectgender:plan:6months:{app_user.telegram_id}",
        f"selectgender:free:{app_user.telegram_id}",
        f"selectgender:back:{app_user.telegram_id}",
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
@pytest.mark.parametrize(
    ("callback_data", "expected_code"),
    [
        ("selectgender:plan:week:1001", "vip_week"),
        ("selectgender:plan:month:1001", "vip_month"),
        ("selectgender:plan:6months:1001", "vip_6months"),
    ],
)
async def test_plan_callbacks_send_matching_vip_invoices(
    callback_data: str,
    expected_code: str,
) -> None:
    callback = FakeCallbackQuery(
        data=callback_data,
        message=FakeMessage(bot=FakeBot()),
        from_user=SimpleNamespace(id=1001),
    )
    payment_service = FakePaymentService()

    await preview_vip_plan(callback, build_user(1), FakeUserService(), payment_service)

    assert payment_service.requested_codes == [expected_code]
    assert callback.message.invoices == [
        {
            "title": f"{expected_code} title",
            "description": f"{expected_code} description",
            "payload": f"payload:{expected_code}",
            "currency": "XTR",
            "prices": [],
            "start_parameter": f"buy-{expected_code}",
        }
    ]
    assert callback.answered == [{"text": "Invoice sent", "show_alert": False}]


@pytest.mark.asyncio
async def test_plan_callbacks_fall_back_to_coming_soon_when_checkout_unavailable() -> None:
    callback = FakeCallbackQuery(
        data="selectgender:plan:week:1001",
        message=FakeMessage(bot=FakeBot()),
        from_user=SimpleNamespace(id=1001),
    )
    payment_service = FakePaymentService(fail=True)

    await preview_vip_plan(callback, build_user(1), FakeUserService(), payment_service)

    assert payment_service.requested_codes == ["vip_week"]
    assert callback.message.invoices == []
    assert callback.message.edits == []
    assert callback.answered == [{"text": VIP_CHECKOUT_COMING_SOON_TEXT, "show_alert": True}]


@pytest.mark.asyncio
async def test_get_free_vip_opens_referral_screen() -> None:
    callback = FakeCallbackQuery(
        data="selectgender:free:1001",
        message=FakeMessage(bot=FakeBot("mybot")),
        from_user=SimpleNamespace(id=1001),
    )
    app_user = build_user(1, referral_code="FREEVIP42", points_balance=2)

    await open_select_gender_referral(callback, app_user, FakeUserService(referral_count=1))

    assert callback.answered == [{"text": None, "show_alert": False}]
    assert callback.message.edits == [
        {
            "text": build_referral_premium_text("mybot", "FREEVIP42", 2, 1),
            "reply_markup": premium_gender_referral_keyboard(app_user.telegram_id),
        }
    ]


@pytest.mark.asyncio
async def test_get_free_vip_handles_missing_bot_username() -> None:
    callback = FakeCallbackQuery(
        data="selectgender:free:1001",
        message=FakeMessage(bot=FakeBot(None)),
        from_user=SimpleNamespace(id=1001),
    )

    await open_select_gender_referral(callback, build_user(1), FakeUserService())

    assert callback.answered == [{"text": INVITE_UNAVAILABLE_TEXT, "show_alert": True}]
    assert callback.message.edits == []


@pytest.mark.asyncio
async def test_exchange_points_for_premium_succeeds_and_opens_gender_selection() -> None:
    callback = FakeCallbackQuery(
        data="selectgender:referral:exchange:1001",
        message=FakeMessage(bot=FakeBot()),
        from_user=SimpleNamespace(id=1001),
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
        data="selectgender:referral:exchange:1001",
        message=FakeMessage(bot=FakeBot()),
        from_user=SimpleNamespace(id=1001),
    )
    app_user = build_user(1, points_balance=2)

    await exchange_points_for_select_gender_premium(callback, app_user, FakeUserService())

    assert callback.answered == [
        {"text": "Need 3 points to unlock 6 hours of premium", "show_alert": True}
    ]
    assert callback.message.edits == []


@pytest.mark.asyncio
async def test_legacy_wallet_callback_is_rejected() -> None:
    callback = FakeCallbackQuery(
        data="selectgender:referral:wallet",
        message=FakeMessage(bot=FakeBot("mybot")),
        from_user=SimpleNamespace(id=1001),
    )

    await handle_legacy_referral_wallet_callback(callback, build_user(1), FakeUserService())

    assert callback.message.edits == []
    assert callback.answered == [{"text": PREMIUM_SCREEN_UNAVAILABLE_TEXT, "show_alert": True}]


@pytest.mark.asyncio
async def test_referral_screen_back_returns_to_premium_gate() -> None:
    callback = FakeCallbackQuery(
        data="selectgender:referral:back:1001",
        message=FakeMessage(bot=FakeBot()),
        from_user=SimpleNamespace(id=1001),
    )
    app_user = build_user(1)

    await return_to_select_gender_gate(callback, app_user, FakeUserService())

    assert callback.answered == [{"text": None, "show_alert": False}]
    assert callback.message.edits == [
        {
            "text": build_premium_gender_gate_text(),
            "reply_markup": premium_gender_gate_keyboard(app_user.telegram_id),
        }
    ]


@pytest.mark.asyncio
async def test_premium_gate_back_returns_to_home_copy() -> None:
    callback = FakeCallbackQuery(
        data="selectgender:back:1001",
        message=FakeMessage(bot=FakeBot()),
        from_user=SimpleNamespace(id=1001),
    )

    await close_select_gender_gate(callback, build_user(1), FakeUserService())

    assert callback.answered == [{"text": None, "show_alert": False}]
    assert callback.message.edits == [{"text": RETURNING_HOME_TEXT, "reply_markup": None}]


def test_select_gender_flow_keeps_main_menu_layout_intact() -> None:
    texts = _reply_keyboard_texts(main_menu_keyboard())
    assert texts == ["Start Chat", "Profile", SELECT_GENDER_BUTTON_TEXT, "Safety", "Help"]


@pytest.mark.asyncio
async def test_user_a_get_free_vip_does_not_edit_user_b_message() -> None:
    callback_a = FakeCallbackQuery(
        data="selectgender:free:1001",
        message=FakeMessage(bot=FakeBot("mybot")),
        from_user=SimpleNamespace(id=1001),
    )
    message_b = FakeMessage(bot=FakeBot("mybot"))
    user_a = build_user(1, referral_code="FREEVIP42", points_balance=2)
    user_b = build_user(2, referral_code="FREEVIP99", points_balance=4)

    await open_select_gender_referral(callback_a, user_a, FakeUserService(referral_count=1))

    assert callback_a.message.edits == [
        {
            "text": build_referral_premium_text("mybot", "FREEVIP42", 2, 1),
            "reply_markup": premium_gender_referral_keyboard(user_a.telegram_id),
        }
    ]
    assert message_b.edits == []
    assert user_b.points_balance == 4


@pytest.mark.asyncio
async def test_foreign_get_free_vip_callback_is_rejected() -> None:
    foreign_user = build_user(2)
    callback = FakeCallbackQuery(
        data="selectgender:free:1001",
        message=FakeMessage(bot=FakeBot("mybot")),
        from_user=SimpleNamespace(id=foreign_user.telegram_id),
    )

    await open_select_gender_referral(callback, foreign_user, FakeUserService())

    assert callback.answered == [{"text": PREMIUM_SCREEN_UNAVAILABLE_TEXT, "show_alert": True}]
    assert callback.message.edits == []


@pytest.mark.asyncio
async def test_foreign_back_callback_is_rejected() -> None:
    foreign_user = build_user(2)
    callback = FakeCallbackQuery(
        data="selectgender:back:1001",
        message=FakeMessage(bot=FakeBot()),
        from_user=SimpleNamespace(id=foreign_user.telegram_id),
    )

    await close_select_gender_gate(callback, foreign_user, FakeUserService())

    assert callback.message.edits == []
    assert callback.answered == [{"text": PREMIUM_SCREEN_UNAVAILABLE_TEXT, "show_alert": True}]


@pytest.mark.asyncio
async def test_foreign_plan_callback_is_rejected_without_invoice() -> None:
    foreign_user = build_user(2)
    callback = FakeCallbackQuery(
        data="selectgender:plan:week:1001",
        message=FakeMessage(bot=FakeBot()),
        from_user=SimpleNamespace(id=foreign_user.telegram_id),
    )
    payment_service = FakePaymentService()

    await preview_vip_plan(callback, foreign_user, FakeUserService(), payment_service)

    assert payment_service.requested_codes == []
    assert callback.message.invoices == []
    assert callback.answered == [{"text": PREMIUM_SCREEN_UNAVAILABLE_TEXT, "show_alert": True}]


@pytest.mark.asyncio
async def test_foreign_exchange_callback_is_rejected_without_state_change() -> None:
    foreign_user = build_user(2, points_balance=7)
    callback = FakeCallbackQuery(
        data="selectgender:referral:exchange:1001",
        message=FakeMessage(bot=FakeBot()),
        from_user=SimpleNamespace(id=foreign_user.telegram_id),
    )

    await exchange_points_for_select_gender_premium(callback, foreign_user, FakeUserService())

    assert foreign_user.points_balance == 7
    assert foreign_user.vip_until is None
    assert callback.message.edits == []
    assert callback.answered == [{"text": PREMIUM_SCREEN_UNAVAILABLE_TEXT, "show_alert": True}]


@pytest.mark.asyncio
async def test_legacy_ownerless_callback_is_rejected() -> None:
    app_user = build_user(1)
    callback = FakeCallbackQuery(
        data="selectgender:free",
        message=FakeMessage(bot=FakeBot("mybot")),
        from_user=SimpleNamespace(id=app_user.telegram_id),
    )

    await open_select_gender_referral(callback, app_user, FakeUserService())

    assert callback.answered == [{"text": PREMIUM_SCREEN_UNAVAILABLE_TEXT, "show_alert": True}]
    assert callback.message.edits == []
