from __future__ import annotations

import asyncio

import pytest
from aiogram.types import User as TelegramUser
from sqlalchemy import select

from app.db.models import Gender, PreferredGender, QueueStatus, Session, SessionStatus, WaitingQueue
from app.utils.exceptions import ConflictError, UserVisibleError


async def register_user(
    services,
    *,
    telegram_id: int,
    first_name: str,
    username: str,
    gender: Gender,
    preferred_gender: PreferredGender,
) -> TelegramUser:
    telegram_user = TelegramUser(
        id=telegram_id,
        is_bot=False,
        first_name=first_name,
        username=username,
    )
    await services.user_service.complete_registration(
        telegram_user,
        age=24,
        gender=gender,
        nickname=None,
        preferred_gender=preferred_gender,
        interests=[],
    )
    return telegram_user


async def get_active_sessions(services) -> list[Session]:
    async with services.session_factory() as session:
        result = await session.execute(
            select(Session).where(Session.status == SessionStatus.ACTIVE)
        )
        return list(result.scalars().all())


async def get_active_waiting_entries(services) -> list[WaitingQueue]:
    async with services.session_factory() as session:
        result = await session.execute(
            select(WaitingQueue).where(WaitingQueue.status == QueueStatus.WAITING)
        )
        return list(result.scalars().all())


@pytest.mark.asyncio
async def test_matchmaking_soft_preferences_and_duplicate_queue_protection(services) -> None:
    user_a = await register_user(
        services,
        telegram_id=2001,
        first_name="A",
        username="user_a",
        gender=Gender.FEMALE,
        preferred_gender=PreferredGender.MALE,
    )
    user_b = await register_user(
        services,
        telegram_id=2002,
        first_name="B",
        username="user_b",
        gender=Gender.FEMALE,
        preferred_gender=PreferredGender.ANY,
    )

    result_a = await services.match_service.enqueue_user(user_a)
    assert result_a.waiting is True

    with pytest.raises(ConflictError):
        await services.match_service.enqueue_user(user_a)

    services.settings.match_soft_preference_after_seconds = 0
    result_b = await services.match_service.enqueue_user(user_b)

    assert result_b.matched is True
    assert result_b.session_id is not None
    assert await services.match_service.is_waiting(user_a.id) is False


@pytest.mark.asyncio
async def test_lone_user_cannot_match_with_self(services) -> None:
    user = await register_user(
        services,
        telegram_id=2101,
        first_name="Solo",
        username="solo_user",
        gender=Gender.MALE,
        preferred_gender=PreferredGender.ANY,
    )

    result = await services.match_service.enqueue_user(user)

    assert result.waiting is True
    assert result.matched is False
    active_sessions = await get_active_sessions(services)
    waiting_entries = await get_active_waiting_entries(services)
    user_record = await services.user_service.require_registered_user(user.id)
    assert active_sessions == []
    assert len(waiting_entries) == 1
    assert waiting_entries[0].user_id == user_record.id


@pytest.mark.asyncio
async def test_user_in_active_session_cannot_enqueue_again(services) -> None:
    user_a = await register_user(
        services,
        telegram_id=2201,
        first_name="A",
        username="active_a",
        gender=Gender.MALE,
        preferred_gender=PreferredGender.ANY,
    )
    user_b = await register_user(
        services,
        telegram_id=2202,
        first_name="B",
        username="active_b",
        gender=Gender.FEMALE,
        preferred_gender=PreferredGender.ANY,
    )

    await services.match_service.enqueue_user(user_a)
    result_b = await services.match_service.enqueue_user(user_b)

    assert result_b.matched is True
    with pytest.raises(ConflictError):
        await services.match_service.enqueue_user(user_a)


@pytest.mark.asyncio
async def test_banned_user_cannot_enqueue(services) -> None:
    user = await register_user(
        services,
        telegram_id=2301,
        first_name="Banned",
        username="banned_user",
        gender=Gender.FEMALE,
        preferred_gender=PreferredGender.ANY,
    )
    registered_user = await services.user_service.require_registered_user(user.id)
    await services.user_service.mark_banned_state(registered_user.id, True)

    with pytest.raises(UserVisibleError):
        await services.match_service.enqueue_user(user)

    assert await services.match_service.is_waiting(user.id) is False
    assert await get_active_sessions(services) == []


@pytest.mark.asyncio
async def test_concurrent_enqueue_creates_single_active_session_without_waiting_leaks(services) -> None:
    user_a = await register_user(
        services,
        telegram_id=2401,
        first_name="ConcurrentA",
        username="concurrent_a",
        gender=Gender.MALE,
        preferred_gender=PreferredGender.ANY,
    )
    user_b = await register_user(
        services,
        telegram_id=2402,
        first_name="ConcurrentB",
        username="concurrent_b",
        gender=Gender.FEMALE,
        preferred_gender=PreferredGender.ANY,
    )

    results = await asyncio.gather(
        services.match_service.enqueue_user(user_a),
        services.match_service.enqueue_user(user_b),
    )

    active_sessions = await get_active_sessions(services)
    waiting_entries = await get_active_waiting_entries(services)
    assert len(active_sessions) == 1
    assert waiting_entries == []

    session = active_sessions[0]
    assert {session.user1_id, session.user2_id} == {
        (await services.user_service.require_registered_user(user_a.id)).id,
        (await services.user_service.require_registered_user(user_b.id)).id,
    }
    assert sum(1 for result in results if result.matched) == 1
    assert any(result.waiting for result in results)
    assert await services.match_service.is_waiting(user_a.id) is False
    assert await services.match_service.is_waiting(user_b.id) is False

    user_a_record = await services.user_service.require_registered_user(user_a.id)
    user_b_record = await services.user_service.require_registered_user(user_b.id)
    assert user_a_record.is_in_chat is True
    assert user_b_record.is_in_chat is True
