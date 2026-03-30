from __future__ import annotations

from contextlib import asynccontextmanager
from types import SimpleNamespace

import pytest

from app.bot.keyboards.chat import active_chat_keyboard
from app.services.match_service import MatchService
from app.utils.enums import PreferredGender, QueueStatus
from app.utils.text import SEARCH_CANCEL_BUTTON_TEXT

from tests.conftest import FakeBot, FakeOpsService, FakeSession, build_user


class FakeUserRepository:
    def __init__(self, users):
        self.users = users

    async def get_by_id(self, user_id: int):
        return self.users.get(user_id)


class FakeWaitingQueueRepository:
    def __init__(self) -> None:
        self.active: dict[int, SimpleNamespace] = {}
        self.status_history: list[tuple[int, QueueStatus]] = []
        self.session = FakeSession()

    async def get_active_by_user_id(self, user_id: int):
        return self.active.get(user_id)

    async def get_active_by_user_id_for_update(self, user_id: int):
        return self.active.get(user_id)

    async def add_waiting(self, user_id: int):
        entry = SimpleNamespace(user_id=user_id, status=QueueStatus.WAITING, match_attempts=0)
        self.active[user_id] = entry
        return entry

    async def update_status(self, user_id: int, status: QueueStatus) -> None:
        self.status_history.append((user_id, status))
        if status == QueueStatus.WAITING:
            self.active[user_id] = SimpleNamespace(user_id=user_id, status=status, match_attempts=0)
        else:
            self.active.pop(user_id, None)

    async def increment_attempts(self, user_id: int) -> None:
        if user_id in self.active:
            self.active[user_id].match_attempts += 1


class FakeSessionRepository:
    def __init__(self) -> None:
        self.active: dict[int, object] = {}

    async def get_active_by_user_id(self, user_id: int):
        return self.active.get(user_id)

    async def get_active_by_user_id_for_update(self, user_id: int):
        return self.active.get(user_id)


class FakeSessionService:
    def __init__(self) -> None:
        self.created_pairs: list[tuple[int, int]] = []

    async def create_session(self, user1_id: int, user2_id: int):
        ordered_pair = tuple(sorted((user1_id, user2_id)))
        self.created_pairs.append(ordered_pair)
        return SimpleNamespace(id=len(self.created_pairs), user1_id=ordered_pair[0], user2_id=ordered_pair[1])


class FakeQueueService:
    def __init__(self) -> None:
        self.queue: list[int] = []
        self.joined_at: dict[int, float] = {}

    @asynccontextmanager
    async def user_lock(self, user_id: int):
        yield True

    @asynccontextmanager
    async def matchmaking_lock(self):
        yield True

    @asynccontextmanager
    async def multi_user_lock(self, user_ids):
        yield True

    async def enqueue_user(self, user) -> None:
        if user.id not in self.queue:
            self.queue.append(user.id)
            self.joined_at[user.id] = float(len(self.joined_at) + 1)

    async def remove_user(self, user_id: int) -> None:
        self.queue = [item for item in self.queue if item != user_id]
        self.joined_at.pop(user_id, None)

    async def is_queued(self, user_id: int) -> bool:
        return user_id in self.queue

    async def get_waiting_user_ids(self, limit: int) -> list[int]:
        return self.queue[:limit]

    async def get_joined_timestamp(self, user_id: int) -> float | None:
        return self.joined_at.get(user_id)


def _reply_keyboard_texts(markup) -> list[str]:
    if markup is None:
        return []
    return [button.text for row in markup.keyboard for button in row]


@pytest.mark.asyncio
async def test_matchmaking_matches_compatible_users_once() -> None:
    bot = FakeBot()
    users = {
        1: build_user(1, gender="male", preferred_gender="female", interests=["memes"]),
        2: build_user(
            2,
            gender="female",
            preferred_gender="male",
            interests=["games", "late night chats"],
            rating_score="1.4",
        ),
    }
    waiting_repo = FakeWaitingQueueRepository()
    session_repo = FakeSessionRepository()
    session_service = FakeSessionService()
    queue_service = FakeQueueService()
    ops_service = FakeOpsService()

    service = MatchService(
        bot,
        FakeUserRepository(users),
        waiting_repo,
        session_repo,
        session_service,
        queue_service,
        ops_service,
        match_scan_limit=10,
    )

    first_outcome = await service.start(users[2])
    second_outcome = await service.start(users[1])

    assert first_outcome.status == "queued"
    assert second_outcome.status == "matched"
    assert session_service.created_pairs == [(1, 2)]
    assert queue_service.queue == []
    expected_keyboard = _reply_keyboard_texts(active_chat_keyboard())
    assert all(
        _reply_keyboard_texts(payload.reply_markup) == expected_keyboard
        for payload in bot.message_payloads
    )
    assert all(
        _reply_keyboard_texts(payload.reply_markup) != [SEARCH_CANCEL_BUTTON_TEXT]
        for payload in bot.message_payloads
    )
    assert ops_service.search_starts == 2
    assert ops_service.matches_created == 1
    sent_messages = {chat_id: text for chat_id, text in bot.messages}
    assert "\U0001f4da Interests: Games, Late Night Chats" in sent_messages[users[1].telegram_id]
    assert "\U0001f3c6 Rating: 1.4" in sent_messages[users[1].telegram_id]
    assert "\U0001f4da Interests: Memes" in sent_messages[users[2].telegram_id]
    assert "\U0001f3c6 Rating: new" in sent_messages[users[2].telegram_id]


@pytest.mark.asyncio
async def test_matchmaking_skips_incompatible_candidate() -> None:
    bot = FakeBot()
    users = {
        1: build_user(1, gender="male", preferred_gender="female", vip_active=True),
        2: build_user(2, gender="male", preferred_gender="male"),
    }
    waiting_repo = FakeWaitingQueueRepository()
    session_repo = FakeSessionRepository()
    session_service = FakeSessionService()
    queue_service = FakeQueueService()
    ops_service = FakeOpsService()

    service = MatchService(
        bot,
        FakeUserRepository(users),
        waiting_repo,
        session_repo,
        session_service,
        queue_service,
        ops_service,
        match_scan_limit=10,
    )

    await service.start(users[2])
    outcome = await service.start(users[1])

    assert outcome.status == "queued"
    assert session_service.created_pairs == []


@pytest.mark.asyncio
async def test_matchmaking_ignores_preference_for_non_vip_users() -> None:
    bot = FakeBot()
    users = {
        1: build_user(1, gender="male", preferred_gender="female"),
        2: build_user(2, gender="male", preferred_gender="male"),
    }
    waiting_repo = FakeWaitingQueueRepository()
    session_repo = FakeSessionRepository()
    session_service = FakeSessionService()
    queue_service = FakeQueueService()
    ops_service = FakeOpsService()

    service = MatchService(
        bot,
        FakeUserRepository(users),
        waiting_repo,
        session_repo,
        session_service,
        queue_service,
        ops_service,
        match_scan_limit=10,
    )

    await service.start(users[2])
    outcome = await service.start(users[1])

    assert outcome.status == "matched"
    assert session_service.created_pairs == [(1, 2)]


@pytest.mark.asyncio
async def test_matchmaking_never_self_matches() -> None:
    bot = FakeBot()
    users = {1: build_user(1, gender="other", preferred_gender=PreferredGender.ANY)}
    waiting_repo = FakeWaitingQueueRepository()
    session_repo = FakeSessionRepository()
    session_service = FakeSessionService()
    queue_service = FakeQueueService()
    ops_service = FakeOpsService()

    service = MatchService(
        bot,
        FakeUserRepository(users),
        waiting_repo,
        session_repo,
        session_service,
        queue_service,
        ops_service,
        match_scan_limit=10,
    )

    outcome = await service.start(users[1])

    assert outcome.status == "queued"
    assert session_service.created_pairs == []


@pytest.mark.asyncio
async def test_cancel_waiting_removes_user_from_queue() -> None:
    bot = FakeBot()
    user = build_user(1, gender="male", preferred_gender="female")
    waiting_repo = FakeWaitingQueueRepository()
    session_repo = FakeSessionRepository()
    session_service = FakeSessionService()
    queue_service = FakeQueueService()
    ops_service = FakeOpsService()

    service = MatchService(
        bot,
        FakeUserRepository({1: user}),
        waiting_repo,
        session_repo,
        session_service,
        queue_service,
        ops_service,
        match_scan_limit=10,
    )

    outcome = await service.start(user)
    cancelled = await service.cancel_waiting(user.id)

    assert outcome.status == "queued"
    assert cancelled is True
    assert queue_service.queue == []
    assert await waiting_repo.get_active_by_user_id(user.id) is None
    assert waiting_repo.status_history[-1] == (user.id, QueueStatus.CANCELLED)
    assert ops_service.cancels == 1


@pytest.mark.asyncio
async def test_repeated_start_does_not_duplicate_queue_entries() -> None:
    bot = FakeBot()
    user = build_user(1, gender="female", preferred_gender="male")
    waiting_repo = FakeWaitingQueueRepository()
    session_repo = FakeSessionRepository()
    session_service = FakeSessionService()
    queue_service = FakeQueueService()
    ops_service = FakeOpsService()

    service = MatchService(
        bot,
        FakeUserRepository({1: user}),
        waiting_repo,
        session_repo,
        session_service,
        queue_service,
        ops_service,
        match_scan_limit=10,
    )

    first = await service.start(user)
    second = await service.start(user)

    assert first.status == "queued"
    assert second.status == "queued"
    assert queue_service.queue == [user.id]
