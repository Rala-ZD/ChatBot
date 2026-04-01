from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
from types import SimpleNamespace

import pytest

from app.bot.handlers.referral import exchange_points_from_referral_tab, points_handler
from app.bot.keyboards.premium import premium_points_exchange_keyboard
from app.services.exceptions import ValidationError
from app.services.user_service import REFERRAL_REWARD_POINTS, VIP_COST_POINTS, UserService
from app.utils.text import INVITE_UNAVAILABLE_TEXT, build_referral_premium_text, build_vip_unlocked_text
from app.utils.time import utcnow

from tests.conftest import FakeRedis, FakeSession, build_user


class FakeUserRepository:
    def __init__(self, users: dict[int, object]) -> None:
        self.users = users
        self.session = FakeSession()

    async def save(self, user):
        self.users[user.id] = user
        return user

    async def get_by_id(self, user_id: int):
        return self.users.get(user_id)

    async def get_by_id_for_update(self, user_id: int):
        return self.users.get(user_id)

    async def get_by_referral_code(self, referral_code: str):
        normalized = referral_code.upper()
        for user in self.users.values():
            if getattr(user, "referral_code", "").upper() == normalized:
                return user
        return None

    async def count_registered_referrals(self, user_id: int) -> int:
        return sum(
            1
            for user in self.users.values()
            if getattr(user, "referred_by_user_id", None) == user_id and getattr(user, "is_registered", False)
        )


class FakeUserService(UserService):
    def __init__(self, repository, settings, redis) -> None:
        super().__init__(repository, settings, redis)


@dataclass
class FakeBot:
    username: str | None = "testbot"

    async def get_me(self):
        return SimpleNamespace(username=self.username)


@dataclass
class FakeMessage:
    bot: FakeBot
    answers: list[dict[str, object | None]]

    async def answer(self, text: str, reply_markup=None, **_: object) -> None:
        self.answers.append({"text": text, "reply_markup": reply_markup})

    async def edit_text(self, text: str, reply_markup=None, **_: object) -> None:
        self.answers.append({"text": text, "reply_markup": reply_markup})


@dataclass
class FakeCallbackQuery:
    data: str
    message: FakeMessage | None
    answered: list[dict[str, object | None]]

    async def answer(self, text: str | None = None, show_alert: bool = False) -> None:
        self.answered.append({"text": text, "show_alert": show_alert})


@pytest.mark.asyncio
async def test_apply_referral_code_sets_inviter_once(settings) -> None:
    inviter = build_user(1, referral_code="ABC123XYZ9")
    referred = build_user(2, is_registered=False, referral_code="NEWCODE123")
    repository = FakeUserRepository({1: inviter, 2: referred})
    service = UserService(repository, settings, FakeRedis())

    await service.apply_referral_code_if_eligible(referred, "ref_abc123xyz9", is_new_user=True)
    await service.apply_referral_code_if_eligible(referred, "ref_OTHERCODE", is_new_user=True)

    assert referred.referred_by_user_id == inviter.id
    assert repository.session.commits == 1


@pytest.mark.asyncio
async def test_registration_rewards_inviter_only_once(settings) -> None:
    inviter = build_user(1, points_balance=2)
    referred = build_user(2, is_registered=False, referred_by_user_id=1)
    repository = FakeUserRepository({1: inviter, 2: referred})
    service = UserService(repository, settings, FakeRedis())

    payload = SimpleNamespace(
        age=22,
        gender=referred.gender,
        nickname="Sky",
        preferred_gender=referred.preferred_gender,
        interests=["music"],
    )

    await service.register_user(referred, payload)
    await service.register_user(referred, payload)

    assert inviter.points_balance == 2 + REFERRAL_REWARD_POINTS
    assert repository.session.commits == 2


@pytest.mark.asyncio
async def test_purchase_vip_deducts_points_and_extends(settings) -> None:
    user = build_user(1, points_balance=25)
    repository = FakeUserRepository({1: user})
    service = UserService(repository, settings, FakeRedis())

    first = await service.purchase_vip(user)
    first_points_balance = first.points_balance
    first_expiry = first.vip_until
    second = await service.purchase_vip(user)

    assert first_points_balance == 25 - VIP_COST_POINTS
    assert second.points_balance == 25 - (VIP_COST_POINTS * 2)
    assert first_expiry is not None
    assert second.vip_until is not None
    assert first_expiry >= utcnow() + timedelta(hours=6)
    assert second.vip_until == first_expiry + timedelta(hours=6)


@pytest.mark.asyncio
async def test_purchase_vip_rejects_low_balance(settings) -> None:
    user = build_user(1, points_balance=2)
    repository = FakeUserRepository({1: user})
    service = UserService(repository, settings, FakeRedis())

    with pytest.raises(ValidationError):
        await service.purchase_vip(user)


@pytest.mark.asyncio
async def test_points_handler_shows_referral_summary_and_exchange_only(settings) -> None:
    inviter = build_user(1, points_balance=4, referral_code="REF1234567")
    referred = build_user(2, referred_by_user_id=1, is_registered=True)
    repository = FakeUserRepository({1: inviter, 2: referred})
    service = FakeUserService(repository, settings, FakeRedis())
    message = FakeMessage(bot=FakeBot("testbot"), answers=[])

    await points_handler(message, inviter, service)

    assert message.answers == [
        {
            "text": build_referral_premium_text("testbot", "REF1234567", 4, 1),
            "reply_markup": premium_points_exchange_keyboard(),
        }
    ]
    texts = [button.text for row in message.answers[0]["reply_markup"].inline_keyboard for button in row]
    assert texts == ["✨ Exchange 3 Points for 6 Hours"]
    assert "Buy Points" not in message.answers[0]["text"]
    assert "Points Wallet" not in message.answers[0]["text"]
    assert "Referral TOP" not in message.answers[0]["text"]


@pytest.mark.asyncio
async def test_points_handler_handles_missing_bot_username(settings) -> None:
    user = build_user(1)
    repository = FakeUserRepository({1: user})
    service = FakeUserService(repository, settings, FakeRedis())
    message = FakeMessage(bot=FakeBot(None), answers=[])

    await points_handler(message, user, service)

    assert message.answers == [{"text": INVITE_UNAVAILABLE_TEXT, "reply_markup": None}]


@pytest.mark.asyncio
async def test_exchange_points_from_referral_tab_succeeds(settings) -> None:
    user = build_user(1, points_balance=3)
    repository = FakeUserRepository({1: user})
    service = FakeUserService(repository, settings, FakeRedis())
    callback = FakeCallbackQuery(
        data="referral:exchange",
        message=FakeMessage(bot=FakeBot(), answers=[]),
        answered=[],
    )

    await exchange_points_from_referral_tab(callback, user, service)

    assert callback.answered == [{"text": None, "show_alert": False}]
    assert user.points_balance == 0
    assert callback.message.answers == [
        {
            "text": build_vip_unlocked_text(user.points_balance, user.vip_until),
            "reply_markup": None,
        }
    ]


@pytest.mark.asyncio
async def test_exchange_points_from_referral_tab_rejects_low_balance(settings) -> None:
    user = build_user(1, points_balance=2)
    repository = FakeUserRepository({1: user})
    service = FakeUserService(repository, settings, FakeRedis())
    callback = FakeCallbackQuery(
        data="referral:exchange",
        message=FakeMessage(bot=FakeBot(), answers=[]),
        answered=[],
    )

    await exchange_points_from_referral_tab(callback, user, service)

    assert callback.answered == [
        {"text": "Need 3 points to unlock 6 hours of premium", "show_alert": True}
    ]
    assert callback.message.answers == []
