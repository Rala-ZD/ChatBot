from __future__ import annotations

from dataclasses import dataclass, field
from types import SimpleNamespace

import pytest

from app.bot.handlers.chat import end_chat, next_stranger
from app.bot.handlers.matchmaking import start_chat
from app.bot.handlers.menu import cancel_action
from app.bot.handlers.start import start_command
from app.bot.keyboards.chat import active_chat_keyboard
from app.bot.keyboards.common import main_menu_keyboard, searching_keyboard
from app.bot.states.registration import RegistrationStates
from app.schemas.common import MatchOutcome
from app.utils.enums import EndReason
from app.utils.text import (
    NO_ACTIVE_SEARCH_TEXT,
    NO_ACTIVE_CHAT_TEXT,
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
        self.data: dict[str, object] = {}

    async def get_state(self) -> str | None:
        return self.current_state

    async def set_state(self, value: object) -> None:
        self.current_state = str(value)

    async def update_data(self, **kwargs: object) -> None:
        self.data.update(kwargs)

    async def clear(self) -> None:
        self.current_state = None
        self.cleared = True
        self.data.clear()


class FakeUserService:
    def __init__(self) -> None:
        self.apply_calls: list[tuple[int | None, bool]] = []

    async def apply_referral_code_if_eligible(self, user, start_argument, *, is_new_user: bool) -> None:
        self.apply_calls.append((user.id if user is not None else None, is_new_user))


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
    def __init__(
        self,
        active_sessions: list[object | None] | None = None,
        *,
        end_result: object | None = SimpleNamespace(session_id=99),
    ) -> None:
        self.active_sessions = active_sessions or [None]
        self.end_calls: list[tuple[int, EndReason, int | None]] = []
        self.end_result = end_result

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
        return self.end_result


def _reply_keyboard_texts(markup) -> list[str]:
    if markup is None:
        return []
    return [button.text for row in markup.keyboard for button in row]


@pytest.mark.asyncio
async def test_searching_keyboard_contains_only_cancel() -> None:
    markup = searching_keyboard()
    assert _reply_keyboard_texts(markup) == [SEARCH_CANCEL_BUTTON_TEXT]


def test_searching_text_uses_premium_waiting_copy() -> None:
    assert SEARCHING_TEXT == (
        "🔎 Finding someone for you...\n\n"
        "💡 Tip: Be friendly — first message matters 😉\n"
        "⏳ Usually takes 3–10 seconds"
    )


@pytest.mark.asyncio
async def test_start_chat_shows_search_keyboard_when_queued() -> None:
    message = FakeMessage(text="Start Chat")
    app_user = build_user(1)

    await start_chat(message, app_user, FakeMatchService(MatchOutcome(status="queued")))

    assert message.answers[-1].text == SEARCHING_TEXT
    assert _reply_keyboard_texts(message.answers[-1].reply_markup) == [SEARCH_CANCEL_BUTTON_TEXT]


@pytest.mark.asyncio
async def test_registered_start_command_matches_start_chat_behavior() -> None:
    message = FakeMessage(text="/start")
    app_user = build_user(1)
    state = FakeState(current_state=RegistrationStates.awaiting_age.state)
    match_service = FakeMatchService(MatchOutcome(status="queued"))
    user_service = FakeUserService()

    await start_command(message, state, app_user, False, user_service, match_service, None)

    assert state.cleared is True
    assert user_service.apply_calls == [(app_user.id, False)]
    assert match_service.started_user_ids == [app_user.id]
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
async def test_cancel_command_restores_chat_keyboard_if_match_already_exists() -> None:
    message = FakeMessage(text="/cancel")
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


@pytest.mark.asyncio
@pytest.mark.parametrize("text", ["/next", "Next"])
async def test_next_command_and_button_share_same_behavior(text: str) -> None:
    message = FakeMessage(text=text)
    app_user = build_user(1)
    session_service = FakeSessionService()
    match_service = FakeMatchService(MatchOutcome(status="queued"))

    await next_stranger(message, app_user, session_service, match_service)

    assert session_service.end_calls == [(app_user.id, EndReason.NEXT, app_user.id)]
    assert message.answers[-1].text == SEARCHING_TEXT
    assert _reply_keyboard_texts(message.answers[-1].reply_markup) == [SEARCH_CANCEL_BUTTON_TEXT]


@pytest.mark.asyncio
@pytest.mark.parametrize("text", ["/end", "End"])
async def test_end_command_and_button_share_same_behavior(text: str) -> None:
    message = FakeMessage(text=text)
    app_user = build_user(1)
    session_service = FakeSessionService(end_result=None)

    await end_chat(message, app_user, session_service)

    assert session_service.end_calls == [(app_user.id, EndReason.END, app_user.id)]
    assert message.answers[-1].text == NO_ACTIVE_CHAT_TEXT
    assert _reply_keyboard_texts(message.answers[-1].reply_markup) == _reply_keyboard_texts(
        main_menu_keyboard()
    )


@pytest.mark.asyncio
async def test_cancel_clears_active_form_state_for_command_and_button() -> None:
    for text in ("/cancel", SEARCH_CANCEL_BUTTON_TEXT):
        message = FakeMessage(text=text)
        state = FakeState(current_state="profile:editing")

        await cancel_action(message, state, build_user(1), FakeMatchService(), FakeSessionService())

        assert state.cleared is True
        assert message.answers[-1].text == "Cancelled."
