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
    REGION_PROMPT_TEXT,
    REGISTRATION_SUCCESS_TEXT,
    accept_rules,
    collect_age,
    collect_gender,
    collect_region,
    finish_interests,
    ignore_typed_age,
    return_to_gender_from_region,
    skip_interests,
    toggle_interest,
)
from app.bot.handlers.start import start_command
from app.bot.keyboards.common import main_menu_keyboard
from app.bot.keyboards.registration import age_keyboard, interests_keyboard, region_keyboard
from app.bot.states.registration import RegistrationStates
from app.utils.text import REGISTRATION_STEP_UNAVAILABLE_TEXT, RULES_TEXT, WELCOME_TEXT
from tests.conftest import build_user


def _reply_keyboard_texts(markup) -> list[str]:
    if markup is None:
        return []
    return [button.text for row in markup.keyboard for button in row]


def _inline_keyboard_texts(markup) -> list[str]:
    if markup is None:
        return []
    return [button.text for row in markup.inline_keyboard for button in row]


def _inline_keyboard_callback_data(markup) -> list[str]:
    if markup is None:
        return []
    return [button.callback_data for row in markup.inline_keyboard for button in row]


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
        user.match_region = payload.match_region
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
    from_user: SimpleNamespace
    answered: list[dict[str, object | None]] = field(default_factory=list)

    async def answer(self, text: str | None = None, show_alert: bool = False, **_: object) -> None:
        self.answered.append({"text": text, "show_alert": show_alert})


@pytest.mark.asyncio
async def test_start_tracks_prompt_message_id_for_new_user_with_owned_consent_button() -> None:
    state = FakeState()
    bot = FakeBotApi()
    message = FakeMessage(bot=bot, chat_id=123, message_id=1, text="/start")
    app_user = build_user(1, is_registered=False)

    await start_command(message, state, app_user, True, FakeUserService(), SimpleNamespace(), None)

    assert state.current_state == RegistrationStates.awaiting_consent
    assert state.data["prompt_message_id"] == message.answers[-1].message_id
    assert message.answers[-1].text == f"{WELCOME_TEXT}\n\n{RULES_TEXT}"
    assert _inline_keyboard_callback_data(message.answers[-1].reply_markup) == [
        f"register:consent:{app_user.telegram_id}"
    ]


@pytest.mark.asyncio
async def test_accept_rules_edits_existing_prompt_into_age_step() -> None:
    state = FakeState()
    app_user = build_user(1, is_registered=False)
    await state.set_state(RegistrationStates.awaiting_consent)
    await state.update_data(prompt_message_id=10)
    prompt_message = FakeMessage(bot=FakeBotApi(), chat_id=123, message_id=10)
    callback = FakeCallbackQuery(
        data=f"register:consent:{app_user.telegram_id}",
        message=prompt_message,
        from_user=SimpleNamespace(id=app_user.telegram_id),
    )

    await accept_rules(callback, state, app_user)

    assert state.current_state == RegistrationStates.awaiting_age
    assert prompt_message.edits[-1]["text"] == AGE_PROMPT_TEXT
    assert _inline_keyboard_texts(prompt_message.edits[-1]["reply_markup"]) == [
        "Under 18 years old",
        "From 18 to 21 years old",
        "From 22 to 25 years old",
        "From 26 to 45 years old",
    ]
    assert state.data["prompt_message_id"] == 10


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("callback_data", "expected_age"),
    [
        ("register:age:under18:1001", 17),
        ("register:age:18_21:1001", 18),
        ("register:age:22_25:1001", 22),
        ("register:age:26_45:1001", 26),
    ],
)
async def test_collect_age_maps_bucket_and_edits_same_prompt_to_gender(
    callback_data: str,
    expected_age: int,
) -> None:
    state = FakeState()
    app_user = build_user(1, is_registered=False)
    await state.set_state(RegistrationStates.awaiting_age)
    await state.update_data(prompt_message_id=11)
    prompt_message = FakeMessage(bot=FakeBotApi(), chat_id=123, message_id=11)
    callback = FakeCallbackQuery(
        data=callback_data,
        message=prompt_message,
        from_user=SimpleNamespace(id=app_user.telegram_id),
    )
    service = FakeUserService()

    await collect_age(callback, state, app_user, service)

    assert state.current_state == RegistrationStates.awaiting_gender
    assert state.data["age"] == expected_age
    assert service.parsed_ages == [str(expected_age)]
    assert prompt_message.answers == []
    assert prompt_message.edits[-1]["text"] == GENDER_PROMPT_TEXT
    assert _inline_keyboard_callback_data(prompt_message.edits[-1]["reply_markup"]) == [
        f"register:gender:male:{app_user.telegram_id}",
        f"register:gender:female:{app_user.telegram_id}",
        f"register:gender:other:{app_user.telegram_id}",
    ]


@pytest.mark.asyncio
async def test_collect_age_rejects_ownerless_callback() -> None:
    state = FakeState()
    app_user = build_user(1, is_registered=False)
    await state.set_state(RegistrationStates.awaiting_age)
    prompt_message = FakeMessage(bot=FakeBotApi(), chat_id=123, message_id=11)
    callback = FakeCallbackQuery(
        data="register:age:22_25",
        message=prompt_message,
        from_user=SimpleNamespace(id=app_user.telegram_id),
    )

    await collect_age(callback, state, app_user, FakeUserService())

    assert state.current_state == RegistrationStates.awaiting_age
    assert prompt_message.edits == []
    assert callback.answered == [
        {"text": REGISTRATION_STEP_UNAVAILABLE_TEXT, "show_alert": True}
    ]


@pytest.mark.asyncio
async def test_collect_gender_moves_to_region_step() -> None:
    state = FakeState()
    app_user = build_user(1, is_registered=False)
    await state.set_state(RegistrationStates.awaiting_gender)
    prompt_message = FakeMessage(bot=FakeBotApi(), chat_id=123, message_id=15)
    callback = FakeCallbackQuery(
        data=f"register:gender:female:{app_user.telegram_id}",
        message=prompt_message,
        from_user=SimpleNamespace(id=app_user.telegram_id),
    )

    await collect_gender(callback, state, app_user)

    assert state.current_state == RegistrationStates.awaiting_region
    assert state.data["gender"] == "female"
    assert state.data["interests"] == []
    assert prompt_message.edits[-1]["text"] == REGION_PROMPT_TEXT
    region_texts = _inline_keyboard_texts(prompt_message.edits[-1]["reply_markup"])
    assert "🇱🇰 Sri Lanka" in region_texts
    assert region_texts[-1] == "↩️ Back"


@pytest.mark.asyncio
async def test_collect_region_stores_slug_and_moves_to_interests() -> None:
    state = FakeState()
    app_user = build_user(1, is_registered=False)
    await state.set_state(RegistrationStates.awaiting_region)
    await state.update_data(age=22, gender="female", interests=[])
    prompt_message = FakeMessage(bot=FakeBotApi(), chat_id=123, message_id=16)
    callback = FakeCallbackQuery(
        data=f"register:region:sri_lanka:{app_user.telegram_id}",
        message=prompt_message,
        from_user=SimpleNamespace(id=app_user.telegram_id),
    )

    await collect_region(callback, state, app_user)

    assert state.current_state == RegistrationStates.awaiting_interests
    assert state.data["match_region"] == "sri_lanka"
    assert prompt_message.edits[-1]["text"] == INTERESTS_PROMPT_TEXT
    assert "Skip" in _inline_keyboard_texts(prompt_message.edits[-1]["reply_markup"])
    assert "Done" in _inline_keyboard_texts(prompt_message.edits[-1]["reply_markup"])


@pytest.mark.asyncio
async def test_region_back_returns_to_gender_step() -> None:
    state = FakeState()
    app_user = build_user(1, is_registered=False)
    await state.set_state(RegistrationStates.awaiting_region)
    prompt_message = FakeMessage(bot=FakeBotApi(), chat_id=123, message_id=16)
    callback = FakeCallbackQuery(
        data=f"register:region:back:{app_user.telegram_id}",
        message=prompt_message,
        from_user=SimpleNamespace(id=app_user.telegram_id),
    )

    await return_to_gender_from_region(callback, state, app_user)

    assert state.current_state == RegistrationStates.awaiting_gender
    assert prompt_message.edits[-1]["text"] == GENDER_PROMPT_TEXT


@pytest.mark.asyncio
async def test_foreign_region_callback_is_rejected_without_advancing_other_user() -> None:
    state = FakeState()
    app_user = build_user(2, is_registered=False)
    await state.set_state(RegistrationStates.awaiting_region)
    prompt_message = FakeMessage(bot=FakeBotApi(), chat_id=123, message_id=16)
    callback = FakeCallbackQuery(
        data="register:region:sri_lanka:1001",
        message=prompt_message,
        from_user=SimpleNamespace(id=app_user.telegram_id),
    )

    await collect_region(callback, state, app_user)

    assert state.current_state == RegistrationStates.awaiting_region
    assert "match_region" not in state.data
    assert prompt_message.edits == []
    assert callback.answered == [
        {"text": REGISTRATION_STEP_UNAVAILABLE_TEXT, "show_alert": True}
    ]


@pytest.mark.asyncio
async def test_typed_age_message_does_not_advance_registration() -> None:
    message = FakeMessage(bot=FakeBotApi(), chat_id=123, message_id=20, text="25")

    await ignore_typed_age(message)

    assert message.deleted is True


@pytest.mark.asyncio
async def test_one_users_registration_state_does_not_touch_another_users_state() -> None:
    first_state = FakeState()
    second_state = FakeState()
    first_user = build_user(1, is_registered=False)
    second_user = build_user(2, is_registered=False)
    await first_state.set_state(RegistrationStates.awaiting_region)
    await first_state.update_data(age=24, gender="female", interests=[])
    await second_state.set_state(RegistrationStates.awaiting_age)
    await second_state.update_data(age=31, prompt_message_id=77)

    prompt_message = FakeMessage(bot=FakeBotApi(), chat_id=123, message_id=22)
    callback = FakeCallbackQuery(
        data=f"register:region:brazil:{first_user.telegram_id}",
        message=prompt_message,
        from_user=SimpleNamespace(id=first_user.telegram_id),
    )

    await collect_region(callback, first_state, first_user)

    assert first_state.current_state == RegistrationStates.awaiting_interests
    assert first_state.data["match_region"] == "brazil"
    assert second_state.current_state == RegistrationStates.awaiting_age
    assert second_state.data == {"age": 31, "prompt_message_id": 77}
    assert second_user.match_region is None


@pytest.mark.asyncio
async def test_interest_toggle_updates_state_and_button_labels() -> None:
    state = FakeState()
    app_user = build_user(1, is_registered=False)
    await state.set_state(RegistrationStates.awaiting_interests)
    await state.update_data(interests=[])
    prompt_message = FakeMessage(bot=FakeBotApi(), chat_id=123, message_id=22)
    callback = FakeCallbackQuery(
        data=f"register:interest:toggle:music:{app_user.telegram_id}",
        message=prompt_message,
        from_user=SimpleNamespace(id=app_user.telegram_id),
    )

    await toggle_interest(callback, state, app_user)

    assert state.data["interests"] == ["music"]
    texts = _inline_keyboard_texts(prompt_message.edits[-1]["reply_markup"])
    assert "✅ Music" in texts

    await toggle_interest(callback, state, app_user)

    assert state.data["interests"] == []
    texts = _inline_keyboard_texts(prompt_message.edits[-1]["reply_markup"])
    assert "Music" in texts
    assert "✅ Music" not in texts


@pytest.mark.asyncio
async def test_skip_completes_registration_with_region_and_empty_interests() -> None:
    state = FakeState()
    app_user = build_user(1, is_registered=False)
    await state.set_state(RegistrationStates.awaiting_interests)
    await state.update_data(
        age=25,
        gender="other",
        match_region="sri_lanka",
        interests=[],
        prompt_message_id=44,
    )
    prompt_message = FakeMessage(bot=FakeBotApi(), chat_id=123, message_id=44)
    callback = FakeCallbackQuery(
        data=f"register:interest:skip:{app_user.telegram_id}",
        message=prompt_message,
        from_user=SimpleNamespace(id=app_user.telegram_id),
    )
    user_service = FakeUserService()

    await skip_interests(callback, state, app_user, user_service)

    assert state.cleared is True
    assert prompt_message.deleted is True
    payload = user_service.register_calls[-1][1]
    assert payload.nickname is None
    assert payload.preferred_gender.value == "any"
    assert payload.match_region == "sri_lanka"
    assert payload.interests == []
    assert callback.message.answers[-1].text == REGISTRATION_SUCCESS_TEXT
    assert _reply_keyboard_texts(callback.message.answers[-1].reply_markup) == _reply_keyboard_texts(
        main_menu_keyboard()
    )


@pytest.mark.asyncio
async def test_done_completes_registration_with_selected_interests_and_region() -> None:
    state = FakeState()
    app_user = build_user(2, is_registered=False)
    await state.set_state(RegistrationStates.awaiting_interests)
    await state.update_data(
        age=28,
        gender="male",
        match_region="global",
        interests=["music", "anime"],
        prompt_message_id=45,
    )
    prompt_message = FakeMessage(bot=FakeBotApi(), chat_id=123, message_id=45)
    callback = FakeCallbackQuery(
        data=f"register:interest:done:{app_user.telegram_id}",
        message=prompt_message,
        from_user=SimpleNamespace(id=app_user.telegram_id),
    )
    user_service = FakeUserService()

    await finish_interests(callback, state, app_user, user_service)

    payload = user_service.register_calls[-1][1]
    assert payload.match_region == "global"
    assert payload.interests == ["music", "anime"]
    assert callback.message.answers[-1].text == REGISTRATION_SUCCESS_TEXT


def test_age_keyboard_uses_tap_friendly_two_column_layout() -> None:
    keyboard = age_keyboard(owner_telegram_id=1001)

    assert _inline_keyboard_texts(keyboard) == [
        "Under 18 years old",
        "From 18 to 21 years old",
        "From 22 to 25 years old",
        "From 26 to 45 years old",
    ]
    assert [len(row) for row in keyboard.inline_keyboard] == [2, 2]


def test_region_keyboard_uses_two_columns_and_back_row() -> None:
    keyboard = region_keyboard(owner_telegram_id=1001)
    texts = _inline_keyboard_texts(keyboard)

    assert texts == [
        "🌍 Global (English)",
        "🇮🇳 India",
        "🇱🇰 Sri Lanka",
        "🇧🇷 Brazil",
        "🇪🇸 Spanish",
        "🇸🇦 Arabic",
        "🇮🇩 Indonesia",
        "🇵🇭 Philippines",
        "🇷🇺 Russia",
        "↩️ Back",
    ]
    assert [len(row) for row in keyboard.inline_keyboard] == [2, 2, 2, 2, 1, 1]


def test_interests_keyboard_marks_selected_options() -> None:
    keyboard = interests_keyboard(["music", "anime"], owner_telegram_id=1001)
    texts = _inline_keyboard_texts(keyboard)

    assert "✅ Music" in texts
    assert "✅ Anime" in texts
    assert texts[-2:] == ["Skip", "Done"]
