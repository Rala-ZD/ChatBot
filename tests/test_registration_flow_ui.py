from __future__ import annotations

from dataclasses import dataclass, field
from types import SimpleNamespace

import pytest
from aiogram.exceptions import TelegramBadRequest
from aiogram.methods import DeleteMessage

from app.bot.handlers.registration import (
    AGE_PROMPT_TEXT,
    GENDER_PROMPT_TEXT,
    INTERESTS_PROMPT_TEXT,
    REGISTRATION_SUCCESS_TEXT,
    accept_rules,
    collect_age,
    collect_gender,
    finish_interests,
    skip_interests,
    toggle_interest,
)
from app.bot.handlers.start import start_command
from app.bot.keyboards.common import main_menu_keyboard
from app.bot.keyboards.registration import interests_keyboard
from app.bot.states.registration import RegistrationStates
from app.utils.text import RULES_TEXT, WELCOME_TEXT
from tests.conftest import build_user


def _reply_keyboard_texts(markup) -> list[str]:
    if markup is None:
        return []
    return [button.text for row in markup.keyboard for button in row]


def _inline_keyboard_texts(markup) -> list[str]:
    if markup is None:
        return []
    return [button.text for row in markup.inline_keyboard for button in row]


class FakeState:
    def __init__(self) -> None:
        self.current_state: object | None = None
        self.data: dict[str, object] = {}
        self.cleared = False

    async def set_state(self, value: object) -> None:
        self.current_state = value

    async def update_data(self, **kwargs: object) -> None:
        self.data.update(kwargs)

    async def get_data(self) -> dict[str, object]:
        return dict(self.data)

    async def clear(self) -> None:
        self.current_state = None
        self.data.clear()
        self.cleared = True


class FakeUserService:
    def __init__(self) -> None:
        self.parsed_ages: list[str] = []
        self.register_calls: list[tuple[int, object]] = []

    async def apply_referral_code_if_eligible(self, *args, **kwargs) -> None:
        return None

    def parse_age(self, raw_value: str) -> int:
        self.parsed_ages.append(raw_value)
        return int(raw_value)

    async def register_user(self, user, payload):
        self.register_calls.append((user.id, payload))
        user.is_registered = True
        return user


@dataclass
class FakeSentMessage:
    message_id: int


class FakeBotApi:
    def __init__(self) -> None:
        self.next_message_id = 100
        self.deleted_messages: list[tuple[int, int]] = []
        self.fail_delete = False

    async def delete_message(self, chat_id: int, message_id: int) -> bool:
        self.deleted_messages.append((chat_id, message_id))
        if self.fail_delete:
            raise TelegramBadRequest(
                DeleteMessage(chat_id=chat_id, message_id=message_id),
                "message can't be deleted",
            )
        return True

    def allocate_message_id(self) -> int:
        self.next_message_id += 1
        return self.next_message_id


@dataclass
class FakeAnsweredMessage:
    text: str
    reply_markup: object | None
    message_id: int


@dataclass
class FakeMessage:
    bot: FakeBotApi
    chat_id: int
    message_id: int
    text: str | None = None
    answers: list[FakeAnsweredMessage] = field(default_factory=list)
    edits: list[dict[str, object | None]] = field(default_factory=list)
    deleted: bool = False
    fail_delete: bool = False
    fail_edit: bool = False

    def __post_init__(self) -> None:
        self.chat = SimpleNamespace(id=self.chat_id)

    async def answer(self, text: str, reply_markup=None, **_: object):
        sent = FakeAnsweredMessage(
            text=text,
            reply_markup=reply_markup,
            message_id=self.bot.allocate_message_id(),
        )
        self.answers.append(sent)
        return FakeSentMessage(message_id=sent.message_id)

    async def edit_text(self, text: str, reply_markup=None, **_: object) -> None:
        if self.fail_edit:
            raise TelegramBadRequest(
                DeleteMessage(chat_id=self.chat_id, message_id=self.message_id),
                "message can't be edited",
            )
        self.edits.append({"text": text, "reply_markup": reply_markup})

    async def delete(self) -> bool:
        self.deleted = True
        if self.fail_delete:
            raise TelegramBadRequest(
                DeleteMessage(chat_id=self.chat_id, message_id=self.message_id),
                "message can't be deleted",
            )
        return True


@dataclass
class FakeCallbackQuery:
    data: str
    message: FakeMessage | None
    answered: list[str | None] = field(default_factory=list)

    async def answer(self, text: str | None = None, **_: object) -> None:
        self.answered.append(text)


@pytest.mark.asyncio
async def test_start_tracks_prompt_message_id_for_new_user() -> None:
    state = FakeState()
    bot = FakeBotApi()
    message = FakeMessage(bot=bot, chat_id=123, message_id=1, text="/start")

    await start_command(message, state, None, False, FakeUserService(), None)

    assert state.current_state == RegistrationStates.awaiting_consent
    assert state.data["prompt_message_id"] == message.answers[-1].message_id
    assert message.answers[-1].text == f"{WELCOME_TEXT}\n\n{RULES_TEXT}"


@pytest.mark.asyncio
async def test_accept_rules_edits_existing_prompt_into_age_step() -> None:
    state = FakeState()
    await state.set_state(RegistrationStates.awaiting_consent)
    await state.update_data(prompt_message_id=10)
    prompt_message = FakeMessage(bot=FakeBotApi(), chat_id=123, message_id=10)
    callback = FakeCallbackQuery(data="register:consent", message=prompt_message)

    await accept_rules(callback, state)

    assert state.current_state == RegistrationStates.awaiting_age
    assert prompt_message.edits[-1]["text"] == AGE_PROMPT_TEXT
    assert state.data["prompt_message_id"] == 10


@pytest.mark.asyncio
async def test_collect_age_deletes_prompt_and_reply_then_shows_gender() -> None:
    bot = FakeBotApi()
    state = FakeState()
    await state.set_state(RegistrationStates.awaiting_age)
    await state.update_data(prompt_message_id=11)
    message = FakeMessage(bot=bot, chat_id=123, message_id=20, text="25")
    service = FakeUserService()

    await collect_age(message, state, service)

    assert state.current_state == RegistrationStates.awaiting_gender
    assert state.data["age"] == 25
    assert bot.deleted_messages == [(123, 11)]
    assert message.deleted is True
    assert message.answers[-1].text == GENDER_PROMPT_TEXT
    assert state.data["prompt_message_id"] == message.answers[-1].message_id


@pytest.mark.asyncio
async def test_collect_age_survives_delete_failures() -> None:
    bot = FakeBotApi()
    bot.fail_delete = True
    state = FakeState()
    await state.set_state(RegistrationStates.awaiting_age)
    await state.update_data(prompt_message_id=11)
    message = FakeMessage(bot=bot, chat_id=123, message_id=20, text="25", fail_delete=True)

    await collect_age(message, state, FakeUserService())

    assert state.current_state == RegistrationStates.awaiting_gender
    assert message.answers[-1].text == GENDER_PROMPT_TEXT


@pytest.mark.asyncio
async def test_gender_callback_moves_directly_to_interests() -> None:
    state = FakeState()
    await state.set_state(RegistrationStates.awaiting_gender)
    prompt_message = FakeMessage(bot=FakeBotApi(), chat_id=123, message_id=15)
    callback = FakeCallbackQuery(data="register:gender:female", message=prompt_message)

    await collect_gender(callback, state)

    assert state.current_state == RegistrationStates.awaiting_interests
    assert state.data["gender"] == "female"
    assert state.data["interests"] == []
    assert prompt_message.edits[-1]["text"] == INTERESTS_PROMPT_TEXT
    assert "Skip" in _inline_keyboard_texts(prompt_message.edits[-1]["reply_markup"])
    assert "Done" in _inline_keyboard_texts(prompt_message.edits[-1]["reply_markup"])


@pytest.mark.asyncio
async def test_interest_toggle_updates_state_and_button_labels() -> None:
    state = FakeState()
    await state.set_state(RegistrationStates.awaiting_interests)
    await state.update_data(interests=[])
    prompt_message = FakeMessage(bot=FakeBotApi(), chat_id=123, message_id=22)
    callback = FakeCallbackQuery(data="register:interest:toggle:music", message=prompt_message)

    await toggle_interest(callback, state)

    assert state.data["interests"] == ["music"]
    texts = _inline_keyboard_texts(prompt_message.edits[-1]["reply_markup"])
    assert "✅ Music" in texts

    await toggle_interest(callback, state)

    assert state.data["interests"] == []
    texts = _inline_keyboard_texts(prompt_message.edits[-1]["reply_markup"])
    assert "Music" in texts
    assert "✅ Music" not in texts


@pytest.mark.asyncio
async def test_skip_completes_registration_with_empty_interests() -> None:
    state = FakeState()
    await state.set_state(RegistrationStates.awaiting_interests)
    await state.update_data(age=25, gender="other", interests=[], prompt_message_id=44)
    prompt_message = FakeMessage(bot=FakeBotApi(), chat_id=123, message_id=44)
    callback = FakeCallbackQuery(data="register:interest:skip", message=prompt_message)
    app_user = build_user(1, is_registered=False)
    user_service = FakeUserService()

    await skip_interests(callback, state, app_user, user_service)

    assert state.cleared is True
    assert prompt_message.deleted is True
    assert user_service.register_calls[-1][1].nickname is None
    assert user_service.register_calls[-1][1].preferred_gender.value == "any"
    assert user_service.register_calls[-1][1].interests == []
    assert callback.message.answers[-1].text == REGISTRATION_SUCCESS_TEXT
    assert _reply_keyboard_texts(callback.message.answers[-1].reply_markup) == _reply_keyboard_texts(
        main_menu_keyboard()
    )


@pytest.mark.asyncio
async def test_done_completes_registration_with_selected_interests() -> None:
    state = FakeState()
    await state.set_state(RegistrationStates.awaiting_interests)
    await state.update_data(age=28, gender="male", interests=["music", "anime"], prompt_message_id=45)
    prompt_message = FakeMessage(bot=FakeBotApi(), chat_id=123, message_id=45)
    callback = FakeCallbackQuery(data="register:interest:done", message=prompt_message)
    app_user = build_user(2, is_registered=False)
    user_service = FakeUserService()

    await finish_interests(callback, state, app_user, user_service)

    payload = user_service.register_calls[-1][1]
    assert payload.interests == ["music", "anime"]
    assert callback.message.answers[-1].text == REGISTRATION_SUCCESS_TEXT


def test_interests_keyboard_marks_selected_options() -> None:
    keyboard = interests_keyboard(["music", "anime"])
    texts = _inline_keyboard_texts(keyboard)

    assert "✅ Music" in texts
    assert "✅ Anime" in texts
    assert texts[-2:] == ["Skip", "Done"]
