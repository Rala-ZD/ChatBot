from __future__ import annotations

from dataclasses import dataclass, field
from types import SimpleNamespace

import pytest

from app.bot.handlers.chat import next_stranger
from app.bot.handlers.matchmaking import start_chat
from app.bot.handlers.menu import cancel_action
from app.bot.keyboards.chat import active_chat_keyboard
from app.bot.keyboards.common import main_menu_keyboard, searching_keyboard
from app.schemas.common import MatchOutcome
from app.utils.enums import EndReason
from app.utils.text import (
    NO_ACTIVE_SEARCH_TEXT,
    SEARCH_CANCEL_BUTTON_TEXT,
    SEARCH_CANCELLED_TEXT,
    SEARCH_MATCHED_TEXT,
    SEARCHING_TEXT,
)
from tests.conftest import build_user


@dataclass
class FakeAnsweredMessage:
    text: str
    reply_markup: object | None = None


@dataclass
class FakeMessage:
    text: str
    answers: list[FakeAnsweredMessage] = field(default_factory=list)

    async def answer(self, text: str, reply_markup=None, **_: object):
        self.answers.append(FakeAnsweredMessage(text=text, reply_markup=reply_markup))
        return SimpleNamespace(message_id=len(self.answers))


class FakeState:
    def __init__(self, current_state: str | None = None) -> None:
        self.current_state = current_state
        self.cleared = False

    async def get_state(self) -> str | None:
        return self.current_state

    async def clear(self) -> None:
        self.current_state = None
        self.cleared = True


class FakeMatchService:
    def __init__(self, outcome: MatchOutcome | None = None, *, cancel_result: bool = False) -> None:
        self.outcome = outcome or MatchOutcome(status="queued")
        self.cancel_result = cancel_result
        self.started_user_ids: list[int] = []
        self.cancelled_user_ids: list[int] = []
        self.waiting_user_ids: set[int] = set()

    async def start(self, user):
        self.started_user_ids.append(user.id)
        if self.outcome.status == "queued":
            self.waiting_user_ids.add(user.id)
        else:
            self.waiting_user_ids.discard(user.id)
        return self.outcome

    async def cancel_waiting(self, user_id: int) -> bool:
        self.cancelled_user_ids.append(user_id)
        if self.cancel_result:
            self.waiting_user_ids.discard(user_id)
        return self.cancel_result

    async def is_waiting(self, user_id: int) -> bool:
        return user_id in self.waiting_user_ids


class FakeSessionService:
    def __init__(self, active_sessions: list[object | None] | None = None) -> None:
        self.active_sessions = active_sessions or [None]
        self.end_calls: list[tuple[int, EndReason, int | None]] = []

    async def get_active_session_for_user(self, user_id: int):
        if len(self.active_sessions) > 1:
            return self.active_sessions.pop(0)
        return self.active_sessions[0]

    async def end_active_session_for_user(
        self,
        user_id: int,
        reason: EndReason,
        *,
        ended_by_user_id: int | None = None,
    ):
        self.end_calls.append((user_id, reason, ended_by_user_id))
        return SimpleNamespace(session_id=99)


def _reply_keyboard_texts(markup) -> list[str]:
    if markup is None:
        return []
    return [button.text for row in markup.keyboard for button in row]


@pytest.mark.asyncio
async def test_searching_keyboard_contains_only_cancel() -> None:
    markup = searching_keyboard()
    assert _reply_keyboard_texts(markup) == [SEARCH_CANCEL_BUTTON_TEXT]


@pytest.mark.asyncio
async def test_start_chat_shows_search_keyboard_when_queued() -> None:
    message = FakeMessage(text="Start Chat")
    app_user = build_user(1)

    await start_chat(message, app_user, FakeMatchService(MatchOutcome(status="queued")))

    assert message.answers[-1].text == SEARCHING_TEXT
    assert _reply_keyboard_texts(message.answers[-1].reply_markup) == [SEARCH_CANCEL_BUTTON_TEXT]


@pytest.mark.asyncio
async def test_cancel_search_restores_main_menu() -> None:
    message = FakeMessage(text=SEARCH_CANCEL_BUTTON_TEXT)
    app_user = build_user(1)
    state = FakeState()
    match_service = FakeMatchService(cancel_result=True)
    session_service = FakeSessionService([None])

    await cancel_action(message, state, app_user, match_service, session_service)

    assert match_service.cancelled_user_ids == [app_user.id]
    assert message.answers[-1].text == SEARCH_CANCELLED_TEXT
    assert _reply_keyboard_texts(message.answers[-1].reply_markup) == _reply_keyboard_texts(
        main_menu_keyboard()
    )


@pytest.mark.asyncio
async def test_stale_cancel_button_restores_chat_keyboard_if_match_already_exists() -> None:
    message = FakeMessage(text=SEARCH_CANCEL_BUTTON_TEXT)
    app_user = build_user(1)
    state = FakeState()
    match_service = FakeMatchService(cancel_result=False)
    session_service = FakeSessionService([None, object()])

    await cancel_action(message, state, app_user, match_service, session_service)

    assert message.answers[-1].text == SEARCH_MATCHED_TEXT
    assert _reply_keyboard_texts(message.answers[-1].reply_markup) == _reply_keyboard_texts(
        active_chat_keyboard()
    )


@pytest.mark.asyncio
async def test_cancel_without_search_restores_main_menu() -> None:
    message = FakeMessage(text=SEARCH_CANCEL_BUTTON_TEXT)
    app_user = build_user(1)
    state = FakeState()
    match_service = FakeMatchService(cancel_result=False)
    session_service = FakeSessionService([None, None])

    await cancel_action(message, state, app_user, match_service, session_service)

    assert message.answers[-1].text == NO_ACTIVE_SEARCH_TEXT
    assert _reply_keyboard_texts(message.answers[-1].reply_markup) == _reply_keyboard_texts(
        main_menu_keyboard()
    )


@pytest.mark.asyncio
async def test_next_shows_search_keyboard_when_requeued() -> None:
    message = FakeMessage(text="Next")
    app_user = build_user(1)
    session_service = FakeSessionService()
    match_service = FakeMatchService(MatchOutcome(status="queued"))

    await next_stranger(message, app_user, session_service, match_service)

    assert message.answers[-1].text == SEARCHING_TEXT
    assert _reply_keyboard_texts(message.answers[-1].reply_markup) == [SEARCH_CANCEL_BUTTON_TEXT]
