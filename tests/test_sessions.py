from __future__ import annotations

import pytest
from aiogram.types import User as TelegramUser

from app.db.models import Gender, PreferredGender, SessionEndReason


@pytest.mark.asyncio
async def test_session_end_marks_users_available_and_exports_once(services, fake_bot) -> None:
    user_a = TelegramUser(id=3001, is_bot=False, first_name="A", username="alpha")
    user_b = TelegramUser(id=3002, is_bot=False, first_name="B", username="beta")

    await services.user_service.complete_registration(
        user_a,
        age=22,
        gender=Gender.MALE,
        nickname="Alpha",
        preferred_gender=PreferredGender.ANY,
        interests=["games"],
    )
    await services.user_service.complete_registration(
        user_b,
        age=23,
        gender=Gender.FEMALE,
        nickname="Beta",
        preferred_gender=PreferredGender.ANY,
        interests=["music"],
    )

    await services.match_service.enqueue_user(user_a)
    matched = await services.match_service.enqueue_user(user_b)

    assert matched.matched is True
    context = await services.session_service.get_active_context_by_telegram_id(user_a.id)
    assert context is not None

    end_result = await services.session_service.end_active_session_by_telegram_id(
        user_a.id,
        SessionEndReason.USER_END,
    )
    assert end_result.ended is True

    ended_again = await services.session_service.end_active_session_by_telegram_id(
        user_a.id,
        SessionEndReason.USER_END,
    )
    assert ended_again.ended is False
    assert len(fake_bot.documents) == 1

    user_after = await services.user_service.require_registered_user(user_a.id)
    partner_after = await services.user_service.require_registered_user(user_b.id)
    assert user_after.is_in_chat is False
    assert partner_after.is_in_chat is False
