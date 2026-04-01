from __future__ import annotations

from dataclasses import dataclass, field
from datetime import timedelta
from types import SimpleNamespace

import pytest

from app.bot.handlers.payments import handle_pre_checkout, handle_successful_payment, send_points_invoice
from app.bot.keyboards.registration import preferred_gender_keyboard
from app.bot.keyboards.payments import points_wallet_keyboard
from app.config import Settings
from app.db.models.point_purchase import PointPurchase
from app.services.payment_service import (
    VIP_6MONTHS_DAYS,
    VIP_MONTH_DAYS,
    VIP_WEEK_DAYS,
    PaymentService,
)
from app.utils.enums import PointPurchaseStatus
from app.utils.text import build_gender_selection_text, build_vip_payment_success_text
from app.utils.time import utcnow

from tests.conftest import FakeOpsService, FakeSession, build_user

VIP_PLAN_STARS = {
    "vip_week": 75,
    "vip_month": 250,
    "vip_6months": 1200,
}

class FakeUserRepository:
    def __init__(self, users: dict[int, object]) -> None:
        self.users = users
        self.session = FakeSession()

    async def get_by_id(self, user_id: int):
        return self.users.get(user_id)

    async def get_by_id_for_update(self, user_id: int):
        return self.users.get(user_id)

    async def save(self, user):
        self.users[user.id] = user
        return user


class FakePointPurchaseRepository:
    def __init__(self) -> None:
        self.session = FakeSession()
        self.purchases: dict[str, PointPurchase] = {}

    async def create(self, purchase: PointPurchase):
        self.purchases[purchase.invoice_payload] = purchase
        return purchase

    async def save(self, purchase: PointPurchase):
        self.purchases[purchase.invoice_payload] = purchase
        return purchase

    async def get_by_invoice_payload(self, invoice_payload: str):
        return self.purchases.get(invoice_payload)

    async def get_by_invoice_payload_for_update(self, invoice_payload: str):
        return self.purchases.get(invoice_payload)


@dataclass
class FakeCallbackMessage:
    invoices: list[dict[str, object]] = field(default_factory=list)
    answers: list[dict[str, object | None]] = field(default_factory=list)
    edits: list[dict[str, object | None]] = field(default_factory=list)

    async def answer_invoice(self, **kwargs: object) -> None:
        self.invoices.append(kwargs)

    async def answer(self, text: str, **kwargs: object) -> None:
        self.answers.append({"text": text, "reply_markup": kwargs.get("reply_markup")})

    async def edit_text(self, text: str, **kwargs: object) -> None:
        self.edits.append({"text": text, "reply_markup": kwargs.get("reply_markup")})


@dataclass
class FakeCallbackQuery:
    data: str
    message: FakeCallbackMessage | None
    answered: list[dict[str, object | None]] = field(default_factory=list)

    async def answer(self, text: str | None = None, show_alert: bool = False) -> None:
        self.answered.append({"text": text, "show_alert": show_alert})


@dataclass
class FakePreCheckoutQuery:
    from_user_id: int
    invoice_payload: str
    currency: str
    total_amount: int
    answered: list[dict[str, object | None]] = field(default_factory=list)

    def __post_init__(self) -> None:
        self.from_user = SimpleNamespace(id=self.from_user_id)

    async def answer(self, ok: bool, error_message: str | None = None, **_: object) -> None:
        self.answered.append({"ok": ok, "error_message": error_message})


@dataclass
class FakePaymentMessage:
    successful_payment: object
    answers: list[dict[str, object | None]] = field(default_factory=list)

    async def answer(self, text: str, **kwargs: object) -> None:
        self.answers.append({"text": text, "reply_markup": kwargs.get("reply_markup")})


PACKAGE_STARS = {10: 25, 50: 100, 150: 250}


def build_payment_service(settings, *, enabled: bool = True):
    configured_settings = settings.model_copy(
        update={
            "payments_enabled": enabled,
            "payments_currency": "XTR",
            "points_package_10_xtr": PACKAGE_STARS[10],
            "points_package_50_xtr": PACKAGE_STARS[50],
            "points_package_150_xtr": PACKAGE_STARS[150],
            "vip_week_xtr": VIP_PLAN_STARS["vip_week"],
            "vip_month_xtr": VIP_PLAN_STARS["vip_month"],
            "vip_6months_xtr": VIP_PLAN_STARS["vip_6months"],
        }
    )
    users = {1: build_user(1, points_balance=3)}
    return (
        PaymentService(
            configured_settings,
            FakeUserRepository(users),
            FakePointPurchaseRepository(),
            FakeOpsService(),
        ),
        users[1],
    )


def test_settings_default_to_disabled_stars_payments(settings) -> None:
    assert settings.payments_enabled is False
    assert settings.payments_currency == "XTR"


def test_settings_require_xtr_when_payments_enabled() -> None:
    with pytest.raises(ValueError, match="PAYMENTS_CURRENCY must be XTR"):
        Settings(
            _env_file=None,
            BOT_TOKEN="1234567890:abcdefghijklmnopqrstuvwxyz",
            WEBHOOK_BASE_URL="https://example.com",
            WEBHOOK_SECRET="super-secret-token",
            WEBHOOK_PATH="/webhook/telegram",
            POSTGRES_DSN="postgresql+asyncpg://postgres:postgres@localhost:5432/chatbot",
            REDIS_DSN="redis://localhost:6379/0",
            ADMIN_CHANNEL_ID=-1001234567890,
            ADMIN_USER_IDS="1,2",
            MINIMUM_AGE=18,
            SUPPORT_USERNAME="supportdesk",
            LOG_LEVEL="INFO",
            PAYMENTS_ENABLED=True,
            PAYMENTS_CURRENCY="USD",
            POINTS_PACKAGE_10_XTR=PACKAGE_STARS[10],
            POINTS_PACKAGE_50_XTR=PACKAGE_STARS[50],
            POINTS_PACKAGE_150_XTR=PACKAGE_STARS[150],
            VIP_WEEK_XTR=VIP_PLAN_STARS["vip_week"],
            VIP_MONTH_XTR=VIP_PLAN_STARS["vip_month"],
            VIP_6MONTHS_XTR=VIP_PLAN_STARS["vip_6months"],
        )


def test_settings_require_all_package_values_when_payments_enabled() -> None:
    with pytest.raises(ValueError, match="POINTS_PACKAGE_50_XTR"):
        Settings(
            _env_file=None,
            BOT_TOKEN="1234567890:abcdefghijklmnopqrstuvwxyz",
            WEBHOOK_BASE_URL="https://example.com",
            WEBHOOK_SECRET="super-secret-token",
            WEBHOOK_PATH="/webhook/telegram",
            POSTGRES_DSN="postgresql+asyncpg://postgres:postgres@localhost:5432/chatbot",
            REDIS_DSN="redis://localhost:6379/0",
            ADMIN_CHANNEL_ID=-1001234567890,
            ADMIN_USER_IDS="1,2",
            MINIMUM_AGE=18,
            SUPPORT_USERNAME="supportdesk",
            LOG_LEVEL="INFO",
            PAYMENTS_ENABLED=True,
            PAYMENTS_CURRENCY="XTR",
            POINTS_PACKAGE_10_XTR=PACKAGE_STARS[10],
            POINTS_PACKAGE_150_XTR=PACKAGE_STARS[150],
            VIP_WEEK_XTR=VIP_PLAN_STARS["vip_week"],
            VIP_MONTH_XTR=VIP_PLAN_STARS["vip_month"],
            VIP_6MONTHS_XTR=VIP_PLAN_STARS["vip_6months"],
        )


@pytest.mark.asyncio
async def test_create_invoice_request_creates_pending_purchase(settings) -> None:
    payment_service, user = build_payment_service(settings)

    invoice = await payment_service.create_invoice_request(user, "points_50")
    purchase = await payment_service.point_purchase_repository.get_by_invoice_payload(invoice.payload)

    assert invoice.title == "50 Points"
    assert invoice.currency == "XTR"
    assert len(invoice.prices) == 1
    assert invoice.prices[0].amount == PACKAGE_STARS[50]
    assert purchase is not None
    assert purchase.package_code == "points_50"
    assert purchase.points_amount == 50
    assert purchase.total_amount_minor == PACKAGE_STARS[50]
    assert purchase.currency == "XTR"
    assert purchase.status == PointPurchaseStatus.PENDING
    assert payment_service.point_purchase_repository.session.commits == 1


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("plan_code", "expected_title", "expected_days", "expected_stars"),
    [
        ("vip_week", "VIP 1 Week", VIP_WEEK_DAYS, VIP_PLAN_STARS["vip_week"]),
        ("vip_month", "VIP 1 Month", VIP_MONTH_DAYS, VIP_PLAN_STARS["vip_month"]),
        ("vip_6months", "VIP 6 Months", VIP_6MONTHS_DAYS, VIP_PLAN_STARS["vip_6months"]),
    ],
)
async def test_create_invoice_request_supports_vip_plans(
    settings,
    plan_code: str,
    expected_title: str,
    expected_days: int,
    expected_stars: int,
) -> None:
    payment_service, user = build_payment_service(settings)

    invoice = await payment_service.create_invoice_request(user, plan_code)
    purchase = await payment_service.point_purchase_repository.get_by_invoice_payload(invoice.payload)

    assert invoice.title == expected_title
    assert invoice.currency == "XTR"
    assert invoice.prices[0].amount == expected_stars
    assert purchase is not None
    assert purchase.package_code == plan_code
    assert purchase.points_amount == 0
    assert purchase.total_amount_minor == expected_stars
    assert purchase.invoice_payload.startswith(f"vip:{plan_code}:")
    assert invoice.start_parameter == f"buy-{plan_code}"
    assert str(expected_days) in invoice.description or expected_title.lower() in invoice.description.lower()


@pytest.mark.asyncio
async def test_pre_checkout_validation_accepts_matching_purchase(settings) -> None:
    payment_service, user = build_payment_service(settings)
    invoice = await payment_service.create_invoice_request(user, "points_10")
    query = FakePreCheckoutQuery(
        from_user_id=user.telegram_id,
        invoice_payload=invoice.payload,
        currency=invoice.currency,
        total_amount=PACKAGE_STARS[10],
    )

    await handle_pre_checkout(query, payment_service)

    assert query.answered == [{"ok": True, "error_message": None}]


@pytest.mark.asyncio
async def test_pre_checkout_validation_rejects_when_payments_disabled(settings) -> None:
    payment_service, user = build_payment_service(settings, enabled=False)
    purchase = PointPurchase(
        id=1,
        user_id=user.id,
        package_code="points_10",
        points_amount=10,
        total_amount_minor=PACKAGE_STARS[10],
        currency="XTR",
        invoice_payload="points:points_10:test",
        status=PointPurchaseStatus.PENDING,
    )
    await payment_service.point_purchase_repository.create(purchase)
    query = FakePreCheckoutQuery(
        from_user_id=user.telegram_id,
        invoice_payload=purchase.invoice_payload,
        currency="XTR",
        total_amount=PACKAGE_STARS[10],
    )

    await handle_pre_checkout(query, payment_service)

    assert query.answered == [{"ok": False, "error_message": "Telegram Stars checkout is unavailable right now."}]


@pytest.mark.asyncio
async def test_pre_checkout_validation_rejects_unknown_payload(settings) -> None:
    payment_service, user = build_payment_service(settings)
    query = FakePreCheckoutQuery(
        from_user_id=user.telegram_id,
        invoice_payload="vip:vip_week:missing",
        currency="XTR",
        total_amount=VIP_PLAN_STARS["vip_week"],
    )

    await handle_pre_checkout(query, payment_service)

    assert query.answered == [{"ok": False, "error_message": "This payment could not be verified."}]


@pytest.mark.asyncio
async def test_pre_checkout_validation_rejects_wrong_currency(settings) -> None:
    payment_service, user = build_payment_service(settings)
    invoice = await payment_service.create_invoice_request(user, "points_10")
    query = FakePreCheckoutQuery(
        from_user_id=user.telegram_id,
        invoice_payload=invoice.payload,
        currency="USD",
        total_amount=PACKAGE_STARS[10],
    )

    await handle_pre_checkout(query, payment_service)

    assert query.answered == [{"ok": False, "error_message": "This payment does not match the selected pack."}]


@pytest.mark.asyncio
async def test_pre_checkout_validation_rejects_wrong_amount_for_vip_plan(settings) -> None:
    payment_service, user = build_payment_service(settings)
    invoice = await payment_service.create_invoice_request(user, "vip_month")
    query = FakePreCheckoutQuery(
        from_user_id=user.telegram_id,
        invoice_payload=invoice.payload,
        currency="XTR",
        total_amount=VIP_PLAN_STARS["vip_month"] + 1,
    )

    await handle_pre_checkout(query, payment_service)

    assert query.answered == [{"ok": False, "error_message": "This payment does not match the selected pack."}]


@pytest.mark.asyncio
async def test_successful_payment_credits_points_once(settings) -> None:
    payment_service, user = build_payment_service(settings)
    invoice = await payment_service.create_invoice_request(user, "points_150")
    payment = SimpleNamespace(
        invoice_payload=invoice.payload,
        currency="XTR",
        total_amount=PACKAGE_STARS[150],
        telegram_payment_charge_id="tg-charge-1",
        provider_payment_charge_id="",
    )

    first = await payment_service.finalize_successful_payment(user, payment)
    second = await payment_service.finalize_successful_payment(user, payment)

    assert first.points_added == 150
    assert first.already_processed is False
    assert second.points_added == 0
    assert second.already_processed is True
    assert first.user.points_balance == 153
    assert payment_service.point_purchase_repository.session.commits == 3


@pytest.mark.asyncio
async def test_successful_vip_payment_activates_for_correct_duration(settings) -> None:
    payment_service, user = build_payment_service(settings)
    before = utcnow()
    invoice = await payment_service.create_invoice_request(user, "vip_week")
    payment = SimpleNamespace(
        invoice_payload=invoice.payload,
        currency="XTR",
        total_amount=VIP_PLAN_STARS["vip_week"],
        telegram_payment_charge_id="tg-vip-week-1",
        provider_payment_charge_id="",
    )

    result = await payment_service.finalize_successful_payment(user, payment)

    assert result.purchase_kind == "vip"
    assert result.already_processed is False
    assert result.vip_was_extended is False
    assert result.user.vip_until is not None
    assert result.user.vip_until >= before + timedelta(days=VIP_WEEK_DAYS)


@pytest.mark.asyncio
async def test_successful_vip_payment_extends_existing_vip(settings) -> None:
    payment_service, user = build_payment_service(settings)
    user.vip_until = utcnow() + timedelta(days=2)
    original_vip_until = user.vip_until
    invoice = await payment_service.create_invoice_request(user, "vip_month")
    payment = SimpleNamespace(
        invoice_payload=invoice.payload,
        currency="XTR",
        total_amount=VIP_PLAN_STARS["vip_month"],
        telegram_payment_charge_id="tg-vip-month-1",
        provider_payment_charge_id="",
    )

    result = await payment_service.finalize_successful_payment(user, payment)

    assert result.purchase_kind == "vip"
    assert result.vip_was_extended is True
    assert result.user.vip_until == original_vip_until + timedelta(days=VIP_MONTH_DAYS)


@pytest.mark.asyncio
async def test_duplicate_successful_vip_payment_does_not_extend_twice(settings) -> None:
    payment_service, user = build_payment_service(settings)
    invoice = await payment_service.create_invoice_request(user, "vip_6months")
    payment = SimpleNamespace(
        invoice_payload=invoice.payload,
        currency="XTR",
        total_amount=VIP_PLAN_STARS["vip_6months"],
        telegram_payment_charge_id="tg-vip-6m-1",
        provider_payment_charge_id="",
    )

    first = await payment_service.finalize_successful_payment(user, payment)
    first_vip_until = first.user.vip_until
    second = await payment_service.finalize_successful_payment(user, payment)

    assert first.already_processed is False
    assert second.already_processed is True
    assert second.purchase_kind == "vip"
    assert second.user.vip_until == first_vip_until


@pytest.mark.asyncio
async def test_package_callback_sends_invoice(settings) -> None:
    payment_service, user = build_payment_service(settings)
    callback_message = FakeCallbackMessage()
    callback = FakeCallbackQuery(
        data="payments:package:points_10",
        message=callback_message,
    )

    await send_points_invoice(
        callback,
        user,
        SimpleNamespace(ensure_registered=lambda _: None),
        payment_service,
    )

    assert len(callback_message.invoices) == 1
    assert callback_message.invoices[0]["title"] == "10 Points"
    assert callback_message.invoices[0]["currency"] == "XTR"
    assert callback_message.invoices[0]["start_parameter"] == "buy-points_10"
    assert len(callback_message.invoices[0]["prices"]) == 1
    assert callback_message.invoices[0]["prices"][0].amount == PACKAGE_STARS[10]
    assert "provider_token" not in callback_message.invoices[0]
    assert callback.answered[-1]["text"] == "Invoice sent"


@pytest.mark.asyncio
async def test_successful_payment_handler_sends_wallet_update(settings) -> None:
    payment_service, user = build_payment_service(settings)
    invoice = await payment_service.create_invoice_request(user, "points_10")
    message = FakePaymentMessage(
        successful_payment=SimpleNamespace(
            invoice_payload=invoice.payload,
            currency="XTR",
            total_amount=PACKAGE_STARS[10],
            telegram_payment_charge_id="tg-charge-2",
            provider_payment_charge_id="",
        )
    )

    await handle_successful_payment(message, user, payment_service)

    assert len(message.answers) == 1
    assert "Added: 10 points" in message.answers[0]["text"]
    assert "Paid with Telegram Stars." in message.answers[0]["text"]
    expected_keyboard = [button.text for row in points_wallet_keyboard().inline_keyboard for button in row]
    actual_keyboard = [button.text for row in message.answers[0]["reply_markup"].inline_keyboard for button in row]
    assert actual_keyboard == expected_keyboard


@pytest.mark.asyncio
async def test_successful_vip_payment_handler_shows_confirmation_and_gender_selection(settings) -> None:
    payment_service, user = build_payment_service(settings)
    invoice = await payment_service.create_invoice_request(user, "vip_week")
    message = FakePaymentMessage(
        successful_payment=SimpleNamespace(
            invoice_payload=invoice.payload,
            currency="XTR",
            total_amount=VIP_PLAN_STARS["vip_week"],
            telegram_payment_charge_id="tg-charge-vip-handler",
            provider_payment_charge_id="",
        )
    )

    await handle_successful_payment(message, user, payment_service)

    assert len(message.answers) == 2
    assert message.answers[0]["text"] == build_vip_payment_success_text(extended=False)
    assert message.answers[1]["text"] == build_gender_selection_text(
        user.preferred_gender,
        user.vip_until,
    )
    expected_keyboard = [
        button.text for row in preferred_gender_keyboard(prefix="selectgender:set").inline_keyboard for button in row
    ]
    actual_keyboard = [
        button.text for row in message.answers[1]["reply_markup"].inline_keyboard for button in row
    ]
    assert actual_keyboard == expected_keyboard
