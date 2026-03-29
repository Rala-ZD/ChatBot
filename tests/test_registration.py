from __future__ import annotations

import pytest
from aiogram.types import User as TelegramUser

from app.db.models import Gender, PreferredGender
from app.utils.exceptions import UserVisibleError


@pytest.mark.asyncio
async def test_registration_validation_and_completion(services) -> None:
    with pytest.raises(UserVisibleError):
        services.user_service.validate_age("15")

    assert services.user_service.validate_interests("Music, coding, Music") == ["music", "coding"]

    telegram_user = TelegramUser(
        id=1001,
        is_bot=False,
        first_name="Alice",
        username="alice",
    )
    user = await services.user_service.complete_registration(
        telegram_user,
        age=21,
        gender=Gender.FEMALE,
        nickname="Ali",
        preferred_gender=PreferredGender.ANY,
        interests=["music", "coding"],
    )

    assert user.is_registered is True
    assert user.consent_accepted_at is not None

    loaded = await services.user_service.require_registered_user(telegram_user.id)
    assert loaded.nickname == "Ali"
    assert loaded.interests_json == ["music", "coding"]
