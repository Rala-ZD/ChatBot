from __future__ import annotations

import pytest

from app.schemas.user import RegistrationPayload
from app.services.exceptions import ValidationError
from app.services.user_service import UserService

from tests.conftest import FakeRedis, FakeSession, build_user


class FakeUserRepository:
    def __init__(self) -> None:
        self.session = FakeSession()

    async def save(self, user):
        return user


def test_parse_age_rejects_underage(settings) -> None:
    service = UserService(FakeUserRepository(), settings, FakeRedis())

    with pytest.raises(ValidationError):
        service.parse_age("17")


def test_normalize_interests_deduplicates(settings) -> None:
    service = UserService(FakeUserRepository(), settings, FakeRedis())
    assert service.normalize_interests("Music, coding, music") == ["music", "coding"]


@pytest.mark.asyncio
async def test_register_user_marks_user_as_registered(settings) -> None:
    repository = FakeUserRepository()
    service = UserService(repository, settings, FakeRedis())
    user = build_user(1, is_registered=False)

    payload = RegistrationPayload(
        age=25,
        gender="other",
        nickname="Nova",
        preferred_gender="any",
        interests=["music", "travel"],
    )

    updated = await service.register_user(user, payload)

    assert updated.is_registered is True
    assert updated.nickname == "Nova"
    assert updated.interests_json == ["music", "travel"]
    assert repository.session.commits == 1
