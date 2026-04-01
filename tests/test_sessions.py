from __future__ import annotations

from contextlib import asynccontextmanager

import pytest

from app.db.models.session import ChatSession
from app.db.models.session_message import SessionMessage
from app.services.session_service import SessionService
from app.utils.enums import DeliveryStatus, EndReason, MessageType, SessionStatus
from app.utils.time import utcnow

from tests.conftest import FakeBot, FakeOpsService, FakeSession, build_user


class FakeSessionRepository:
    def __init__(self, chat_session: ChatSession | None = None) -> None:
        self.chat_session = chat_session
        self.session = FakeSession()
        self.created: list[ChatSession] = []

    async def get_active_by_user_id(self, user_id: int):
        if self.chat_session and self.chat_session.status == SessionStatus.ACTIVE:
            if user_id in {self.chat_session.user1_id, self.chat_session.user2_id}:
                return self.chat_session
        return None

    async def get_active_by_user_id_for_update(self, user_id: int):
        return await self.get_active_by_user_id(user_id)

    async def create(self, user1_id: int, user2_id: int):
        session = ChatSession(id=99, user1_id=user1_id, user2_id=user2_id, status=SessionStatus.ACTIVE)
        self.created.append(session)
        self.chat_session = session
        return session

    async def get_with_details(self, session_id: int):
        if self.chat_session and self.chat_session.id == session_id:
            return self.chat_session
        return None

    async def get_with_details_for_update(self, session_id: int):
        return await self.get_with_details(session_id)

    async def save(self, chat_session: ChatSession):
        self.chat_session = chat_session
        return chat_session


class FakeExportService:
    def __init__(self) -> None:
        self.exported_session_ids: list[int] = []

    async def export_session(self, session_id: int) -> None:
        self.exported_session_ids.append(session_id)


class FakeQueueService:
    @asynccontextmanager
    async def multi_user_lock(self, user_ids):
        yield True


def _inline_keyboard_texts(markup) -> list[str]:
    if markup is None:
        return []
    return [button.text for row in markup.inline_keyboard for button in row]


@pytest.mark.asyncio
async def test_create_session_persists_pair() -> None:
    repository = FakeSessionRepository()
    service = SessionService(
        FakeBot(),
        repository,
        FakeExportService(),
        FakeQueueService(),
        FakeOpsService(),
    )

    created = await service.create_session(2, 1)

    assert created.user1_id == 1
    assert created.user2_id == 2
    assert repository.session.commits == 1


@pytest.mark.asyncio
async def test_end_session_is_idempotent() -> None:
    chat_session = ChatSession(
        id=10,
        user1_id=1,
        user2_id=2,
        status=SessionStatus.ACTIVE,
        started_at=utcnow(),
    )
    chat_session.user1 = build_user(1)
    chat_session.user2 = build_user(2)

    repository = FakeSessionRepository(chat_session)
    export_service = FakeExportService()
    service = SessionService(
        FakeBot(),
        repository,
        export_service,
        FakeQueueService(),
        FakeOpsService(),
    )

    first = await service.end_session(10, EndReason.END, ended_by_user_id=1)
    second = await service.end_session(10, EndReason.END, ended_by_user_id=1)

    assert first.already_ended is False
    assert second.already_ended is True
    assert export_service.exported_session_ids == [10]
    assert repository.chat_session.status == SessionStatus.ENDED


@pytest.mark.asyncio
async def test_end_session_shows_summary_card_only_once_per_user() -> None:
    chat_session = ChatSession(
        id=11,
        user1_id=1,
        user2_id=2,
        status=SessionStatus.ACTIVE,
        started_at=utcnow(),
    )
    chat_session.user1 = build_user(1)
    chat_session.user2 = build_user(2)
    chat_session.messages = [
        SessionMessage(
            id=1,
            session_id=11,
            sender_user_id=1,
            sender_chat_id=1001,
            source_message_id=10,
            message_type=MessageType.TEXT,
            telegram_message_id=10,
            delivery_status=DeliveryStatus.DELIVERED,
            text_content="hi",
        ),
        SessionMessage(
            id=2,
            session_id=11,
            sender_user_id=2,
            sender_chat_id=1002,
            source_message_id=11,
            message_type=MessageType.TEXT,
            telegram_message_id=11,
            delivery_status=DeliveryStatus.FAILED,
            text_content="blocked",
        ),
    ]

    bot = FakeBot()
    service = SessionService(
        bot,
        FakeSessionRepository(chat_session),
        FakeExportService(),
        FakeQueueService(),
        FakeOpsService(),
    )

    await service.end_session(11, EndReason.END, ended_by_user_id=1)

    assert len(bot.message_payloads) == 2
    assert all(payload.text.startswith("❗ The chat is over.") for payload in bot.message_payloads)
    assert all("💬 Messages: 1" in payload.text for payload in bot.message_payloads)
    assert all("Chat Ended" not in payload.text for payload in bot.message_payloads)
    assert all(
        _inline_keyboard_texts(payload.reply_markup)
        == ["😍 Great", "🙂 Okay", "😡 Bad", "🚫 Spam / Ads"]
        for payload in bot.message_payloads
    )


@pytest.mark.asyncio
async def test_next_end_does_not_send_extra_finding_next_match_message_to_initiator() -> None:
    chat_session = ChatSession(
        id=13,
        user1_id=1,
        user2_id=2,
        status=SessionStatus.ACTIVE,
        started_at=utcnow(),
    )
    chat_session.user1 = build_user(1)
    chat_session.user2 = build_user(2)
    chat_session.messages = []

    bot = FakeBot()
    service = SessionService(
        bot,
        FakeSessionRepository(chat_session),
        FakeExportService(),
        FakeQueueService(),
        FakeOpsService(),
    )

    await service.end_session(13, EndReason.NEXT, ended_by_user_id=1)

    assert [payload.chat_id for payload in bot.message_payloads] == [chat_session.user2.telegram_id]
    assert all("Finding your next match..." not in payload.text for payload in bot.message_payloads)
    assert bot.message_payloads[0].text == "👋 Chat Ended\nYour match moved on."


@pytest.mark.asyncio
async def test_report_end_skips_summary_for_reporter() -> None:
    chat_session = ChatSession(
        id=12,
        user1_id=1,
        user2_id=2,
        status=SessionStatus.ACTIVE,
        started_at=utcnow(),
    )
    chat_session.user1 = build_user(1)
    chat_session.user2 = build_user(2)

    bot = FakeBot()
    service = SessionService(
        bot,
        FakeSessionRepository(chat_session),
        FakeExportService(),
        FakeQueueService(),
        FakeOpsService(),
    )

    await service.end_session(12, EndReason.REPORT, ended_by_user_id=1)

    assert [payload.chat_id for payload in bot.message_payloads] == [chat_session.user2.telegram_id]
    assert bot.message_payloads[0].text == "👋 Chat Ended"
