from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.services.exceptions import ValidationError
from app.services.user_service import REFERRAL_REWARD_POINTS, VIP_COST_POINTS, UserService
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

    async def get_by_referral_code(self, referral_code: str):
        normalized = referral_code.upper()
        for user in self.users.values():
            if getattr(user, "referral_code", "").upper() == normalized:
                return user
        return None


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
    assert second.vip_until > first_expiry


@pytest.mark.asyncio
async def test_purchase_vip_rejects_low_balance(settings) -> None:
    user = build_user(1, points_balance=5)
    repository = FakeUserRepository({1: user})
    service = UserService(repository, settings, FakeRedis())

    with pytest.raises(ValidationError):
        await service.purchase_vip(user)
