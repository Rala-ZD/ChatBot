from __future__ import annotations

from dataclasses import dataclass, field
from datetime import timedelta
from types import SimpleNamespace

import pytest

from app.db.models.session import ChatSession
from app.services.relay_service import RelayService
from app.utils.enums import DeliveryStatus, EndReason, MessageType, SessionStatus
from app.utils.text import EARLY_CHAT_RESTRICTION_TEXT
from app.utils.time import utcnow

from tests.conftest import FakeBot, FakeSession, build_user


class FakeUserRepository:
    def __init__(self, users) -> None:
        self.users = users

    async def get_by_id(self, user_id: int):
        return self.users.get(user_id)


class FakeSessionMessageRepository:
    def __init__(self) -> None:
        self.session = FakeSession()
        self.records = []

    async def create(self, message):
        self.records.append(message)
        return message


class FakeRelaySessionService:
    def __init__(self, chat_session: ChatSession) -> None:
        self.chat_session = chat_session
        self.ended_sessions: list[tuple[int, EndReason, int | None]] = []

    async def get_active_session_for_user(self, user_id: int):
        if self.chat_session.status != SessionStatus.ACTIVE:
            return None
        if user_id in {self.chat_session.user1_id, self.chat_session.user2_id}:
            return self.chat_session
        return None

    async def end_session(
        self,
        session_id: int,
        reason: EndReason,
        *,
        ended_by_user_id: int | None = None,
    ) -> None:
        self.ended_sessions.append((session_id, reason, ended_by_user_id))


@dataclass
class FakeIncomingMessage:
    chat_id: int
    message_id: int
    text: str | None = None
    caption: str | None = None
    photo: list[SimpleNamespace] | None = None
    video: SimpleNamespace | None = None
    voice: SimpleNamespace | None = None
    document: SimpleNamespace | None = None
    sticker: SimpleNamespace | None = None
    animation: SimpleNamespace | None = None
    audio: SimpleNamespace | None = None
    video_note: SimpleNamespace | None = None
    answers: list[dict[str, object | None]] = field(default_factory=list)

    def __post_init__(self) -> None:
        self.chat = SimpleNamespace(id=self.chat_id)

    async def answer(self, text: str, **kwargs: object) -> None:
        self.answers.append(
            {
                "text": text,
                "reply_markup": kwargs.get("reply_markup"),
            }
        )


def build_photo_message(*, chat_id: int, message_id: int, caption: str | None = None) -> FakeIncomingMessage:
    return FakeIncomingMessage(
        chat_id=chat_id,
        message_id=message_id,
        caption=caption,
        photo=[
            SimpleNamespace(file_id="photo-small", file_unique_id="photo-small-unique"),
            SimpleNamespace(file_id="photo-large", file_unique_id="photo-large-unique"),
        ],
    )


def build_animation_message(*, chat_id: int, message_id: int) -> FakeIncomingMessage:
    return FakeIncomingMessage(
        chat_id=chat_id,
        message_id=message_id,
        animation=SimpleNamespace(file_id="anim-1", file_unique_id="anim-unique-1"),
    )


def build_service(
    *,
    sender_vip: bool = False,
    started_seconds_ago: int = 30,
) -> tuple[RelayService, FakeBot, FakeSessionMessageRepository, FakeRelaySessionService, object, object]:
    sender = build_user(1, telegram_id=1001, vip_active=sender_vip)
    partner = build_user(2, telegram_id=1002)
    chat_session = ChatSession(
        id=50,
        user1_id=sender.id,
        user2_id=partner.id,
        status=SessionStatus.ACTIVE,
        started_at=utcnow() - timedelta(seconds=started_seconds_ago),
    )

    bot = FakeBot()
    message_repository = FakeSessionMessageRepository()
    session_service = FakeRelaySessionService(chat_session)
    service = RelayService(
        bot,
        FakeUserRepository({sender.id: sender, partner.id: partner}),
        message_repository,
        session_service,
    )
    return service, bot, message_repository, session_service, sender, partner


@pytest.mark.asyncio
async def test_non_premium_plain_text_allowed_during_first_90_seconds() -> None:
    service, bot, message_repository, _, sender, partner = build_service()
    message = FakeIncomingMessage(chat_id=sender.telegram_id, message_id=11, text="Hello there")

    await service.relay_message(sender, message)

    assert bot.copied_messages == [(partner.telegram_id, sender.telegram_id, 11)]
    assert bot.deleted_messages == []
    assert message.answers == []
    assert len(message_repository.records) == 1
    assert message_repository.records[0].delivery_status == DeliveryStatus.DELIVERED
    assert message_repository.records[0].message_type == MessageType.TEXT
    assert message_repository.session.commits == 1


@pytest.mark.asyncio
async def test_non_premium_link_blocked_during_first_90_seconds() -> None:
    service, bot, message_repository, _, sender, _ = build_service()
    message = FakeIncomingMessage(
        chat_id=sender.telegram_id,
        message_id=12,
        text="See https://example.com now",
    )

    await service.relay_message(sender, message)

    assert bot.copied_messages == []
    assert bot.deleted_messages == [(sender.telegram_id, 12)]
    assert message.answers[-1]["text"] == EARLY_CHAT_RESTRICTION_TEXT
    assert message_repository.records[0].delivery_status == DeliveryStatus.FAILED
    assert message_repository.records[0].error_text == "early_chat_restriction:link"
    assert message_repository.records[0].metadata_json["reason"] == "link"


@pytest.mark.asyncio
async def test_non_premium_handle_blocked_during_first_90_seconds() -> None:
    service, bot, message_repository, _, sender, _ = build_service()
    message = FakeIncomingMessage(
        chat_id=sender.telegram_id,
        message_id=13,
        text="Add me at @chatfriend",
    )

    await service.relay_message(sender, message)

    assert bot.copied_messages == []
    assert bot.deleted_messages == [(sender.telegram_id, 13)]
    assert message.answers[-1]["text"] == EARLY_CHAT_RESTRICTION_TEXT
    assert message_repository.records[0].error_text == "early_chat_restriction:handle"


@pytest.mark.asyncio
async def test_non_premium_media_blocked_during_first_90_seconds() -> None:
    service, bot, message_repository, _, sender, _ = build_service()
    message = build_photo_message(chat_id=sender.telegram_id, message_id=14, caption="Look at this")

    await service.relay_message(sender, message)

    assert bot.copied_messages == []
    assert bot.deleted_messages == [(sender.telegram_id, 14)]
    assert message.answers[-1]["text"] == EARLY_CHAT_RESTRICTION_TEXT
    assert message_repository.records[0].message_type == MessageType.PHOTO
    assert message_repository.records[0].error_text == "early_chat_restriction:media"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("message", "expected_type"),
    [
        (
            FakeIncomingMessage(chat_id=1001, message_id=15, text="www.example.com"),
            MessageType.TEXT,
        ),
        (
            build_photo_message(chat_id=1001, message_id=16),
            MessageType.PHOTO,
        ),
    ],
)
async def test_premium_user_can_send_links_and_media_immediately(message, expected_type) -> None:
    service, bot, message_repository, _, sender, partner = build_service(sender_vip=True)
    message.chat.id = sender.telegram_id

    await service.relay_message(sender, message)

    assert bot.copied_messages == [(partner.telegram_id, sender.telegram_id, message.message_id)]
    assert bot.deleted_messages == []
    assert message.answers == []
    assert message_repository.records[0].delivery_status == DeliveryStatus.DELIVERED
    assert message_repository.records[0].message_type == expected_type


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "message",
    [
        FakeIncomingMessage(chat_id=1001, message_id=17, text="Find me at @latefriend"),
        FakeIncomingMessage(chat_id=1001, message_id=18, text="example.com"),
        build_photo_message(chat_id=1001, message_id=19),
    ],
)
async def test_non_premium_user_allowed_after_90_seconds(message) -> None:
    service, bot, message_repository, _, sender, partner = build_service(started_seconds_ago=91)
    message.chat.id = sender.telegram_id

    await service.relay_message(sender, message)

    assert bot.copied_messages == [(partner.telegram_id, sender.telegram_id, message.message_id)]
    assert bot.deleted_messages == []
    assert message.answers == []
    assert message_repository.records[0].delivery_status == DeliveryStatus.DELIVERED


@pytest.mark.asyncio
async def test_blocked_content_is_not_relayed_and_delete_failures_do_not_crash() -> None:
    service, bot, message_repository, _, sender, _ = build_service()
    bot.fail_delete = True
    message = build_animation_message(chat_id=sender.telegram_id, message_id=20)

    await service.relay_message(sender, message)

    assert bot.copied_messages == []
    assert bot.deleted_messages == [(sender.telegram_id, 20)]
    assert message.answers[-1]["text"] == EARLY_CHAT_RESTRICTION_TEXT
    assert message_repository.records[0].delivery_status == DeliveryStatus.FAILED
    assert message_repository.records[0].message_type == MessageType.UNSUPPORTED
    assert message_repository.records[0].error_text == "early_chat_restriction:media"
    assert message_repository.session.commits == 1
