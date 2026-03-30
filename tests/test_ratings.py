from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

import pytest

from app.bot.handlers.moderation import submit_report
from app.db.models.session import ChatSession
from app.services.exceptions import AccessDeniedError, ConflictError
from app.services.rating_service import RatingService
from app.utils.enums import EndReason, SessionRatingValue, SessionStatus
from app.utils.text import REPORT_DONE_TEXT
from app.utils.time import utcnow

from tests.conftest import FakeSession, build_user


class FakeSessionRepository:
    def __init__(self, chat_session: ChatSession | None) -> None:
        self.chat_session = chat_session

    async def get_with_details(self, session_id: int) -> ChatSession | None:
        if self.chat_session and self.chat_session.id == session_id:
            return self.chat_session
        return None


class FakeSessionRatingRepository:
    def __init__(self, session: FakeSession) -> None:
        self.session = session
        self.created_keys: set[tuple[int, int]] = set()

    async def create_if_absent(self, rating) -> bool:
        key = (rating.session_id, rating.from_user_id)
        if key in self.created_keys:
            return False
        self.created_keys.add(key)
        return True


class FakeUserRepository:
    def __init__(self, users: dict[int, object], session: FakeSession) -> None:
        self.users = users
        self.session = session

    async def get_by_id_for_update(self, user_id: int):
        return self.users.get(user_id)

    async def save(self, user):
        self.users[user.id] = user
        return user


def _ended_session(*, partner_rating_score: Decimal | str | None = None) -> tuple[ChatSession, object, object]:
    user1 = build_user(1)
    user2 = build_user(2, rating_score=partner_rating_score)
    chat_session = ChatSession(
        id=55,
        user1_id=user1.id,
        user2_id=user2.id,
        status=SessionStatus.ENDED,
        started_at=utcnow(),
        ended_at=utcnow(),
        end_reason=EndReason.END,
    )
    chat_session.user1 = user1
    chat_session.user2 = user2
    return chat_session, user1, user2


def _rating_service(
    chat_session: ChatSession,
    user1,
    user2,
) -> tuple[RatingService, FakeSessionRatingRepository, FakeUserRepository]:
    session = FakeSession()
    session_rating_repository = FakeSessionRatingRepository(session)
    user_repository = FakeUserRepository({user1.id: user1, user2.id: user2}, session)
    service = RatingService(
        FakeSessionRepository(chat_session),
        session_rating_repository,
        user_repository,
    )
    return service, session_rating_repository, user_repository


@pytest.mark.asyncio
async def test_good_rating_increases_score_by_point_two() -> None:
    chat_session, user1, user2 = _ended_session()
    service, _, user_repository = _rating_service(chat_session, user1, user2)

    result = await service.save_rating(chat_session.id, user1.id, SessionRatingValue.GOOD)

    assert result.already_saved is False
    assert user_repository.users[user2.id].rating_score == Decimal("0.2")


@pytest.mark.asyncio
async def test_bad_rating_decreases_score_by_point_two() -> None:
    chat_session, user1, user2 = _ended_session()
    service, _, user_repository = _rating_service(chat_session, user1, user2)

    await service.save_rating(chat_session.id, user1.id, SessionRatingValue.BAD)

    assert user_repository.users[user2.id].rating_score == Decimal("-0.2")


@pytest.mark.asyncio
async def test_rating_score_is_clamped_to_upper_bound() -> None:
    chat_session, user1, user2 = _ended_session(partner_rating_score="4.9")
    service, _, user_repository = _rating_service(chat_session, user1, user2)

    await service.save_rating(chat_session.id, user1.id, SessionRatingValue.GOOD)

    assert user_repository.users[user2.id].rating_score == Decimal("5.0")


@pytest.mark.asyncio
async def test_rating_score_is_clamped_to_lower_bound() -> None:
    chat_session, user1, user2 = _ended_session(partner_rating_score="-4.9")
    service, _, user_repository = _rating_service(chat_session, user1, user2)

    await service.save_rating(chat_session.id, user1.id, SessionRatingValue.BAD)

    assert user_repository.users[user2.id].rating_score == Decimal("-5.0")


@pytest.mark.asyncio
async def test_duplicate_session_rating_does_not_change_score_twice() -> None:
    chat_session, user1, user2 = _ended_session()
    service, session_rating_repository, user_repository = _rating_service(chat_session, user1, user2)

    first = await service.save_rating(chat_session.id, user1.id, SessionRatingValue.GOOD)
    second = await service.save_rating(chat_session.id, user1.id, SessionRatingValue.GOOD)

    assert first.already_saved is False
    assert second.already_saved is True
    assert user_repository.users[user2.id].rating_score == Decimal("0.2")
    assert session_rating_repository.session.commits == 1


@pytest.mark.asyncio
async def test_non_participant_cannot_rate_chat() -> None:
    chat_session, user1, user2 = _ended_session()
    service, _, _ = _rating_service(chat_session, user1, user2)

    with pytest.raises(AccessDeniedError):
        await service.save_rating(chat_session.id, 999, SessionRatingValue.GOOD)


@pytest.mark.asyncio
async def test_active_session_cannot_be_rated() -> None:
    chat_session, user1, user2 = _ended_session()
    chat_session.status = SessionStatus.ACTIVE
    chat_session.ended_at = None
    service, _, _ = _rating_service(chat_session, user1, user2)

    with pytest.raises(ConflictError):
        await service.save_rating(chat_session.id, user1.id, SessionRatingValue.GOOD)


@dataclass
class FakeMessage:
    text: str
    answers: list[tuple[str, object | None]]

    async def answer(self, text: str, reply_markup=None, **_: object):
        self.answers.append((text, reply_markup))


class FakeState:
    def __init__(self, session_id: int) -> None:
        self.data = {"session_id": session_id}
        self.cleared = False

    async def get_data(self) -> dict[str, int]:
        return self.data

    async def clear(self) -> None:
        self.cleared = True


class FakeModerationService:
    def __init__(self) -> None:
        self.calls: list[tuple[int, int, str]] = []

    async def create_report(self, chat_session: ChatSession, app_user, reason: str) -> None:
        self.calls.append((chat_session.id, app_user.id, reason))


class FakeEndedSessionService:
    def __init__(self, chat_session: ChatSession) -> None:
        self.chat_session = chat_session
        self.end_calls: list[tuple[int, EndReason, int | None]] = []
        self.session_repository = self

    async def get_with_details(self, session_id: int) -> ChatSession | None:
        if self.chat_session.id == session_id:
            return self.chat_session
        return None

    async def end_session(
        self,
        session_id: int,
        reason: EndReason,
        *,
        ended_by_user_id: int | None = None,
    ) -> None:
        self.end_calls.append((session_id, reason, ended_by_user_id))


@pytest.mark.asyncio
async def test_report_submission_for_ended_session_does_not_end_again() -> None:
    chat_session, user1, _ = _ended_session()
    moderation_service = FakeModerationService()
    session_service = FakeEndedSessionService(chat_session)
    state = FakeState(chat_session.id)
    message = FakeMessage(text="spam", answers=[])

    await submit_report(
        message,
        state,
        user1,
        moderation_service,
        session_service,
    )

    assert moderation_service.calls == [(chat_session.id, user1.id, "spam")]
    assert session_service.end_calls == []
    assert state.cleared is True
    assert message.answers[-1][0] == REPORT_DONE_TEXT
