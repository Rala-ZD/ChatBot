from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from types import SimpleNamespace

import pytest

from app.bot.handlers.ratings import report_from_summary
from app.bot.handlers.moderation import submit_report
from app.db.models.session import ChatSession
from app.services.exceptions import AccessDeniedError, ConflictError
from app.services.rating_service import RatingService
from app.utils.enums import EndReason, SessionRatingValue, SessionStatus
from app.utils.text import REPORT_DONE_TEXT
from app.utils.time import utcnow

from tests.conftest import FakeSession, build_user


class FakeSessionRepository:
    def __init__(self, chat_sessions: ChatSession | dict[int, ChatSession] | None) -> None:
        if isinstance(chat_sessions, dict):
            self.chat_sessions = chat_sessions
        elif chat_sessions is None:
            self.chat_sessions = {}
        else:
            self.chat_sessions = {chat_sessions.id: chat_sessions}

    async def get_with_details(self, session_id: int) -> ChatSession | None:
        return self.chat_sessions.get(session_id)

    async def get_with_details_for_user(self, session_id: int, user_id: int) -> ChatSession | None:
        chat_session = self.chat_sessions.get(session_id)
        if chat_session is None:
            return None
        if user_id not in {chat_session.user1_id, chat_session.user2_id}:
            return None
        return chat_session

    async def get_by_id(self, session_id: int) -> ChatSession | None:
        return self.chat_sessions.get(session_id)


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


def _ended_session(
    session_id: int = 55,
    *,
    partner_rating_score: Decimal | str = "5.0",
) -> tuple[ChatSession, object, object]:
    user1 = build_user(1)
    user2 = build_user(2, rating_score=partner_rating_score)
    chat_session = ChatSession(
        id=session_id,
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
    chat_sessions: ChatSession | dict[int, ChatSession],
    users: dict[int, object],
    session_rating_repository: FakeSessionRatingRepository | None = None,
    user_repository: FakeUserRepository | None = None,
) -> tuple[RatingService, FakeSessionRatingRepository, FakeUserRepository]:
    session = FakeSession()
    rating_repository = session_rating_repository or FakeSessionRatingRepository(session)
    repository = user_repository or FakeUserRepository(users, session)
    service = RatingService(
        FakeSessionRepository(chat_sessions),
        rating_repository,
        repository,
    )
    return service, rating_repository, repository


@pytest.mark.asyncio
async def test_new_users_default_to_five_point_zero() -> None:
    assert build_user(1).rating_score == Decimal("5.0")


@pytest.mark.asyncio
async def test_good_rating_keeps_user_at_five_point_zero_ceiling() -> None:
    chat_session, user1, user2 = _ended_session()
    service, _, user_repository = _rating_service(chat_session, {user1.id: user1, user2.id: user2})

    result = await service.save_rating(chat_session.id, user1.id, SessionRatingValue.GOOD)

    assert result.already_saved is False
    assert user_repository.users[user2.id].rating_score == Decimal("5.0")


@pytest.mark.asyncio
async def test_bad_rating_decreases_score_from_five_to_four_point_eight() -> None:
    chat_session, user1, user2 = _ended_session()
    service, _, user_repository = _rating_service(chat_session, {user1.id: user1, user2.id: user2})

    await service.save_rating(chat_session.id, user1.id, SessionRatingValue.BAD)

    assert user_repository.users[user2.id].rating_score == Decimal("4.8")


@pytest.mark.asyncio
async def test_repeated_bad_ratings_reach_floor_in_point_two_steps() -> None:
    partner = build_user(2, rating_score="5.0")
    rater = build_user(1)
    sessions = {
        session_id: ChatSession(
            id=session_id,
            user1_id=rater.id,
            user2_id=partner.id,
            status=SessionStatus.ENDED,
            started_at=utcnow(),
            ended_at=utcnow(),
            end_reason=EndReason.END,
        )
        for session_id in range(100, 160)
    }
    for chat_session in sessions.values():
        chat_session.user1 = rater
        chat_session.user2 = partner

    session = FakeSession()
    rating_repository = FakeSessionRatingRepository(session)
    user_repository = FakeUserRepository({rater.id: rater, partner.id: partner}, session)
    service, _, _ = _rating_service(sessions, user_repository.users, rating_repository, user_repository)

    for session_id in sessions:
        await service.save_rating(session_id, rater.id, SessionRatingValue.BAD)

    assert partner.rating_score == Decimal("-5.0")


@pytest.mark.asyncio
async def test_repeated_good_ratings_reach_ceiling_in_point_two_steps() -> None:
    partner = build_user(2, rating_score="4.0")
    rater = build_user(1)
    sessions = {
        session_id: ChatSession(
            id=session_id,
            user1_id=rater.id,
            user2_id=partner.id,
            status=SessionStatus.ENDED,
            started_at=utcnow(),
            ended_at=utcnow(),
            end_reason=EndReason.END,
        )
        for session_id in range(200, 210)
    }
    for chat_session in sessions.values():
        chat_session.user1 = rater
        chat_session.user2 = partner

    session = FakeSession()
    rating_repository = FakeSessionRatingRepository(session)
    user_repository = FakeUserRepository({rater.id: rater, partner.id: partner}, session)
    service, _, _ = _rating_service(sessions, user_repository.users, rating_repository, user_repository)

    for session_id in sessions:
        await service.save_rating(session_id, rater.id, SessionRatingValue.GOOD)

    assert partner.rating_score == Decimal("5.0")


@pytest.mark.asyncio
async def test_rating_score_is_clamped_to_lower_bound() -> None:
    chat_session, user1, user2 = _ended_session(partner_rating_score="-4.9")
    service, _, user_repository = _rating_service(chat_session, {user1.id: user1, user2.id: user2})

    await service.save_rating(chat_session.id, user1.id, SessionRatingValue.BAD)

    assert user_repository.users[user2.id].rating_score == Decimal("-5.0")


@pytest.mark.asyncio
async def test_duplicate_session_rating_does_not_change_score_twice() -> None:
    chat_session, user1, user2 = _ended_session()
    service, session_rating_repository, user_repository = _rating_service(
        chat_session,
        {user1.id: user1, user2.id: user2},
    )

    first = await service.save_rating(chat_session.id, user1.id, SessionRatingValue.BAD)
    second = await service.save_rating(chat_session.id, user1.id, SessionRatingValue.BAD)

    assert first.already_saved is False
    assert second.already_saved is True
    assert user_repository.users[user2.id].rating_score == Decimal("4.8")
    assert session_rating_repository.session.commits == 1


@pytest.mark.asyncio
async def test_non_participant_cannot_rate_chat() -> None:
    chat_session, user1, user2 = _ended_session()
    service, _, _ = _rating_service(chat_session, {user1.id: user1, user2.id: user2})

    with pytest.raises(AccessDeniedError):
        await service.save_rating(chat_session.id, 999, SessionRatingValue.GOOD)


@pytest.mark.asyncio
async def test_active_session_cannot_be_rated() -> None:
    chat_session, user1, user2 = _ended_session()
    chat_session.status = SessionStatus.ACTIVE
    chat_session.ended_at = None
    service, _, _ = _rating_service(chat_session, {user1.id: user1, user2.id: user2})

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
        self.state: object | None = None

    async def get_data(self) -> dict[str, int]:
        return self.data

    async def set_state(self, value: object) -> None:
        self.state = value

    async def update_data(self, **kwargs: object) -> None:
        self.data.update(kwargs)

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

    async def get_session_for_user(self, session_id: int, user_id: int) -> ChatSession | None:
        if self.chat_session.id != session_id:
            return None
        if user_id not in {self.chat_session.user1_id, self.chat_session.user2_id}:
            return None
        return self.chat_session

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


@pytest.mark.asyncio
async def test_report_submission_rejects_foreign_session_id() -> None:
    chat_session, _, _ = _ended_session()
    moderation_service = FakeModerationService()
    session_service = FakeEndedSessionService(chat_session)
    state = FakeState(chat_session.id)
    message = FakeMessage(text="spam", answers=[])
    outsider = build_user(999)

    with pytest.raises(ConflictError):
        await submit_report(
            message,
            state,
            outsider,
            moderation_service,
            session_service,
        )

    assert moderation_service.calls == []
    assert session_service.end_calls == []


@dataclass
class FakeCallbackMessage:
    answers: list[str] | None = None

    async def answer(self, text: str, **_: object) -> None:
        if self.answers is None:
            self.answers = []
        self.answers.append(text)


@dataclass
class FakeCallbackQuery:
    data: str
    message: FakeCallbackMessage | None = None
    answered: list[dict[str, object]] = None

    def __post_init__(self) -> None:
        if self.answered is None:
            self.answered = []

    async def answer(self, text: str | None = None, show_alert: bool = False) -> None:
        self.answered.append({"text": text, "show_alert": show_alert})


@pytest.mark.asyncio
async def test_report_from_summary_rejects_foreign_session_id() -> None:
    chat_session, user1, _ = _ended_session()
    session_service = FakeEndedSessionService(chat_session)
    callback = FakeCallbackQuery(
        data=f"chatrate:report:{chat_session.id}",
        message=FakeCallbackMessage(),
    )
    state = FakeState(chat_session.id)
    outsider = build_user(999)

    await report_from_summary(callback, state, outsider, session_service)

    assert state.state is None
    assert state.data == {"session_id": chat_session.id}
    assert callback.answered == [{"text": "This chat is no longer available.", "show_alert": True}]
    assert callback.message.answers is None


def test_partner_id_for_rejects_non_participant() -> None:
    chat_session, _, _ = _ended_session()

    with pytest.raises(ValueError):
        chat_session.partner_id_for(999)
