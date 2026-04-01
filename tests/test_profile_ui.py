from __future__ import annotations

from dataclasses import dataclass, field
from types import SimpleNamespace

import pytest
from aiogram.exceptions import TelegramBadRequest
from aiogram.methods import DeleteMessage

from app.bot.handlers.profile import (
    PROFILE_AGE_PROMPT_TEXT,
    PROFILE_CARD_MESSAGE_ID_KEY,
    PROFILE_EDITOR_HEADING_TEXT,
    PROFILE_EDITOR_MESSAGE_ID_KEY,
    PROFILE_EDITOR_UNAVAILABLE_TEXT,
    PROFILE_FILTER_PROMPT_TEXT,
    PROFILE_INTERESTS_PROMPT_TEXT,
    PROFILE_NICKNAME_PROMPT_TEXT,
    _profile_summary,
    finish_profile_interests,
    show_profile,
    start_profile_edit,
    toggle_profile_interest,
    update_age,
    update_gender,
    update_nickname,
    update_preferred_gender,
)
from app.bot.keyboards.profile import profile_edit_keyboard
from app.bot.states.profile import ProfileStates
from app.services.exceptions import ValidationError
from tests.conftest import build_user


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

    async def get_state(self) -> object | None:
        return self.current_state

    async def set_state(self, value: object | None) -> None:
        self.current_state = value

    async def update_data(self, **kwargs: object) -> None:
        self.data.update(kwargs)

    async def get_data(self) -> dict[str, object]:
        return dict(self.data)


@dataclass
class FakeMessage:
    bot: "FakeBotApi"
    chat_id: int
    message_id: int
    text: str | None = None
    reply_markup: object | None = None
    answers: list["FakeMessage"] = field(default_factory=list)
    deleted: bool = False

    def __post_init__(self) -> None:
        self.chat = SimpleNamespace(id=self.chat_id)

    async def answer(self, text: str, reply_markup=None, **_: object) -> "FakeMessage":
        sent = self.bot.create_message(self.chat_id, text, reply_markup)
        self.answers.append(sent)
        return sent

    async def edit_text(self, text: str, reply_markup=None, **_: object) -> "FakeMessage":
        if self.message_id in self.bot.fail_edit_ids:
            raise TelegramBadRequest(
                DeleteMessage(chat_id=self.chat_id, message_id=self.message_id),
                "message can't be edited",
            )
        self.text = text
        self.reply_markup = reply_markup
        return self

    async def delete(self) -> bool:
        self.deleted = True
        if self.message_id in self.bot.fail_delete_ids:
            raise TelegramBadRequest(
                DeleteMessage(chat_id=self.chat_id, message_id=self.message_id),
                "message can't be deleted",
            )
        self.bot.deleted_messages.append((self.chat_id, self.message_id))
        return True


class FakeBotApi:
    def __init__(self) -> None:
        self.next_message_id = 100
        self.messages: dict[int, FakeMessage] = {}
        self.sent_messages: list[FakeMessage] = []
        self.deleted_messages: list[tuple[int, int]] = []
        self.edited_messages: list[tuple[int, int, str]] = []
        self.fail_edit_ids: set[int] = set()
        self.fail_delete_ids: set[int] = set()

    def create_message(self, chat_id: int, text: str, reply_markup=None) -> FakeMessage:
        self.next_message_id += 1
        message = FakeMessage(
            bot=self,
            chat_id=chat_id,
            message_id=self.next_message_id,
            text=text,
            reply_markup=reply_markup,
        )
        self.messages[message.message_id] = message
        self.sent_messages.append(message)
        return message

    async def edit_message_text(
        self,
        *,
        chat_id: int,
        message_id: int,
        text: str,
        reply_markup=None,
    ) -> FakeMessage:
        if message_id in self.fail_edit_ids:
            raise TelegramBadRequest(
                DeleteMessage(chat_id=chat_id, message_id=message_id),
                "message can't be edited",
            )
        message = self.messages[message_id]
        message.text = text
        message.reply_markup = reply_markup
        self.edited_messages.append((chat_id, message_id, text))
        return message

    async def delete_message(self, chat_id: int, message_id: int) -> bool:
        self.deleted_messages.append((chat_id, message_id))
        if message_id in self.fail_delete_ids:
            raise TelegramBadRequest(
                DeleteMessage(chat_id=chat_id, message_id=message_id),
                "message can't be deleted",
            )
        if message_id in self.messages:
            self.messages[message_id].deleted = True
        return True


@dataclass
class FakeCallbackQuery:
    data: str
    message: FakeMessage | None
    from_user: SimpleNamespace
    answered: list[dict[str, object | None]] = field(default_factory=list)

    async def answer(self, text: str | None = None, show_alert: bool = False, **_: object) -> None:
        self.answered.append({"text": text, "show_alert": show_alert})


class FakeUserService:
    def __init__(self) -> None:
        self.updated_fields: list[dict[str, object]] = []

    def parse_age(self, raw_value: str) -> int:
        try:
            age = int(raw_value.strip())
        except ValueError as exc:
            raise ValidationError("Please enter your age as a number.") from exc
        if age < 13 or age > 100:
            raise ValidationError("Please enter a valid age.")
        return age

    def normalize_nickname(self, raw_value: str) -> str | None:
        cleaned = raw_value.strip()
        if not cleaned:
            return None
        if len(cleaned) > 32:
            raise ValidationError("Nickname must be 32 characters or fewer.")
        return cleaned

    async def update_profile(self, user, **updates):
        self.updated_fields.append(dict(updates))
        for field, value in updates.items():
            setattr(user, field, value)
        return user


@pytest.mark.asyncio
async def test_show_profile_sends_profile_card_and_edit_panel() -> None:
    state = FakeState()
    bot = FakeBotApi()
    user = build_user(1, interests=["music"], vip_active=False)
    user.nickname = "Sam"
    message = FakeMessage(bot=bot, chat_id=123, message_id=1, text="/profile")

    await show_profile(message, state, user)

    assert len(bot.sent_messages) == 2
    card_message, editor_message = bot.sent_messages
    assert card_message.text == _profile_summary(user)
    assert card_message.reply_markup is None
    assert editor_message.text == PROFILE_EDITOR_HEADING_TEXT
    assert editor_message.reply_markup == profile_edit_keyboard(user.telegram_id)
    assert state.data[PROFILE_CARD_MESSAGE_ID_KEY] == card_message.message_id
    assert state.data[PROFILE_EDITOR_MESSAGE_ID_KEY] == editor_message.message_id


@pytest.mark.asyncio
async def test_age_edit_uses_existing_editor_panel_and_restores_profile_screen() -> None:
    state = FakeState()
    bot = FakeBotApi()
    user = build_user(2, interests=["music"], vip_active=False)
    message = FakeMessage(bot=bot, chat_id=123, message_id=1, text="/profile")
    service = FakeUserService()

    await show_profile(message, state, user)
    editor_message = bot.sent_messages[1]
    callback = FakeCallbackQuery(
        data=f"profile:edit:age:{user.telegram_id}",
        message=editor_message,
        from_user=SimpleNamespace(id=user.telegram_id),
    )

    await start_profile_edit(callback, state, user)

    assert len(bot.sent_messages) == 2
    assert state.current_state == ProfileStates.editing_age
    assert editor_message.text == PROFILE_AGE_PROMPT_TEXT
    assert editor_message.reply_markup is None

    user_input = FakeMessage(bot=bot, chat_id=123, message_id=2, text="31")
    await update_age(user_input, state, user, service)

    assert user_input.deleted is True
    assert state.current_state is None
    assert len(bot.sent_messages) == 2
    assert "🎂 Age: 31" in bot.messages[state.data[PROFILE_CARD_MESSAGE_ID_KEY]].text
    assert bot.messages[state.data[PROFILE_EDITOR_MESSAGE_ID_KEY]].text == (
        "\u2705 Age updated\n\n\u270f\ufe0f Edit Profile"
    )
    assert _inline_keyboard_texts(bot.messages[state.data[PROFILE_EDITOR_MESSAGE_ID_KEY]].reply_markup) == [
        "\U0001f9d1 Nickname",
        "\U0001f382 Age",
        "\U0001f6b9 Gender",
        "\U0001f3af Filter",
        "\u2728 Interests",
    ]


@pytest.mark.asyncio
async def test_nickname_validation_error_stays_inside_same_panel() -> None:
    state = FakeState()
    bot = FakeBotApi()
    user = build_user(3, interests=[], vip_active=False)
    message = FakeMessage(bot=bot, chat_id=123, message_id=1, text="/profile")
    service = FakeUserService()

    await show_profile(message, state, user)
    editor_message = bot.sent_messages[1]
    callback = FakeCallbackQuery(
        data=f"profile:edit:nickname:{user.telegram_id}",
        message=editor_message,
        from_user=SimpleNamespace(id=user.telegram_id),
    )

    await start_profile_edit(callback, state, user)

    user_input = FakeMessage(bot=bot, chat_id=123, message_id=2, text="x" * 33)
    await update_nickname(user_input, state, user, service)

    assert user_input.deleted is True
    assert state.current_state == ProfileStates.editing_nickname
    assert len(bot.sent_messages) == 2
    assert bot.messages[state.data[PROFILE_EDITOR_MESSAGE_ID_KEY]].text == (
        "\u274c Nickname must be 32 characters or fewer.\n\nSend your nickname"
    )


@pytest.mark.asyncio
async def test_gender_edit_saves_and_returns_to_main_panel() -> None:
    state = FakeState()
    bot = FakeBotApi()
    user = build_user(4, gender="other", vip_active=False)
    message = FakeMessage(bot=bot, chat_id=123, message_id=1, text="/profile")
    service = FakeUserService()

    await show_profile(message, state, user)
    editor_message = bot.sent_messages[1]
    open_callback = FakeCallbackQuery(
        data=f"profile:edit:gender:{user.telegram_id}",
        message=editor_message,
        from_user=SimpleNamespace(id=user.telegram_id),
    )
    await start_profile_edit(open_callback, state, user)

    assert state.current_state == ProfileStates.editing_gender
    assert bot.messages[state.data[PROFILE_EDITOR_MESSAGE_ID_KEY]].text == "Select your gender"

    save_callback = FakeCallbackQuery(
        data=f"profile:gender:female:{user.telegram_id}",
        message=editor_message,
        from_user=SimpleNamespace(id=user.telegram_id),
    )
    await update_gender(save_callback, state, user, service)

    assert user.gender.value == "female"
    assert state.current_state is None
    assert len(bot.sent_messages) == 2
    assert "🧑 Gender: Female" in bot.messages[state.data[PROFILE_CARD_MESSAGE_ID_KEY]].text
    assert bot.messages[state.data[PROFILE_EDITOR_MESSAGE_ID_KEY]].text == (
        "\u2705 Gender updated\n\n\u270f\ufe0f Edit Profile"
    )


@pytest.mark.asyncio
async def test_filter_edit_saves_and_returns_to_main_panel() -> None:
    state = FakeState()
    bot = FakeBotApi()
    user = build_user(5, preferred_gender="any", vip_active=False)
    message = FakeMessage(bot=bot, chat_id=123, message_id=1, text="/profile")
    service = FakeUserService()

    await show_profile(message, state, user)
    editor_message = bot.sent_messages[1]
    open_callback = FakeCallbackQuery(
        data=f"profile:edit:preferred_gender:{user.telegram_id}",
        message=editor_message,
        from_user=SimpleNamespace(id=user.telegram_id),
    )
    await start_profile_edit(open_callback, state, user)

    assert state.current_state == ProfileStates.editing_preferred_gender
    assert bot.messages[state.data[PROFILE_EDITOR_MESSAGE_ID_KEY]].text == PROFILE_FILTER_PROMPT_TEXT

    save_callback = FakeCallbackQuery(
        data=f"profile:preferred:male:{user.telegram_id}",
        message=editor_message,
        from_user=SimpleNamespace(id=user.telegram_id),
    )
    await update_preferred_gender(save_callback, state, user, service)

    assert user.preferred_gender.value == "male"
    assert state.current_state is None
    assert "🎯 Match Preference: Male" in bot.messages[state.data[PROFILE_CARD_MESSAGE_ID_KEY]].text
    assert bot.messages[state.data[PROFILE_EDITOR_MESSAGE_ID_KEY]].text == (
        "\u2705 Filter updated\n\n\u270f\ufe0f Edit Profile"
    )


@pytest.mark.asyncio
async def test_interests_edit_toggles_and_saves_in_same_panel() -> None:
    state = FakeState()
    bot = FakeBotApi()
    user = build_user(6, interests=["music"], vip_active=False)
    message = FakeMessage(bot=bot, chat_id=123, message_id=1, text="/profile")
    service = FakeUserService()

    await show_profile(message, state, user)
    editor_message = bot.sent_messages[1]
    open_callback = FakeCallbackQuery(
        data=f"profile:edit:interests:{user.telegram_id}",
        message=editor_message,
        from_user=SimpleNamespace(id=user.telegram_id),
    )
    await start_profile_edit(open_callback, state, user)

    assert state.current_state == ProfileStates.editing_interests
    assert bot.messages[state.data[PROFILE_EDITOR_MESSAGE_ID_KEY]].text == PROFILE_INTERESTS_PROMPT_TEXT
    assert "Done" in _inline_keyboard_texts(bot.messages[state.data[PROFILE_EDITOR_MESSAGE_ID_KEY]].reply_markup)

    toggle_callback = FakeCallbackQuery(
        data=f"profile:interest:toggle:anime:{user.telegram_id}",
        message=editor_message,
        from_user=SimpleNamespace(id=user.telegram_id),
    )
    await toggle_profile_interest(toggle_callback, state, user)

    texts = _inline_keyboard_texts(bot.messages[state.data[PROFILE_EDITOR_MESSAGE_ID_KEY]].reply_markup)
    assert "\u2705 Music" in texts
    assert "\u2705 Anime" in texts

    finish_callback = FakeCallbackQuery(
        data=f"profile:interest:done:{user.telegram_id}",
        message=editor_message,
        from_user=SimpleNamespace(id=user.telegram_id),
    )
    await finish_profile_interests(finish_callback, state, user, service)

    assert user.interests_json == ["music", "anime"]
    assert state.current_state is None
    assert "✨ Interests: music, anime" in bot.messages[state.data[PROFILE_CARD_MESSAGE_ID_KEY]].text
    assert bot.messages[state.data[PROFILE_EDITOR_MESSAGE_ID_KEY]].text == (
        "\u2705 Interests updated\n\n\u270f\ufe0f Edit Profile"
    )


@pytest.mark.asyncio
async def test_reopening_profile_deletes_old_card_and_editor_before_new_pair() -> None:
    state = FakeState()
    bot = FakeBotApi()
    user = build_user(7, vip_active=False)

    first_message = FakeMessage(bot=bot, chat_id=123, message_id=1, text="/profile")
    await show_profile(first_message, state, user)
    old_card_id = state.data[PROFILE_CARD_MESSAGE_ID_KEY]
    old_editor_id = state.data[PROFILE_EDITOR_MESSAGE_ID_KEY]

    second_message = FakeMessage(bot=bot, chat_id=123, message_id=2, text="/profile")
    await show_profile(second_message, state, user)

    assert (123, old_card_id) in bot.deleted_messages
    assert (123, old_editor_id) in bot.deleted_messages
    assert state.data[PROFILE_CARD_MESSAGE_ID_KEY] != old_card_id
    assert state.data[PROFILE_EDITOR_MESSAGE_ID_KEY] != old_editor_id


@pytest.mark.asyncio
async def test_stale_and_foreign_callbacks_are_rejected_safely() -> None:
    state = FakeState()
    bot = FakeBotApi()
    user = build_user(8, vip_active=False)

    first_message = FakeMessage(bot=bot, chat_id=123, message_id=1, text="/profile")
    await show_profile(first_message, state, user)
    stale_editor = bot.sent_messages[1]

    second_message = FakeMessage(bot=bot, chat_id=123, message_id=2, text="/profile")
    await show_profile(second_message, state, user)
    current_editor = bot.messages[state.data[PROFILE_EDITOR_MESSAGE_ID_KEY]]

    stale_callback = FakeCallbackQuery(
        data=f"profile:edit:age:{user.telegram_id}",
        message=stale_editor,
        from_user=SimpleNamespace(id=user.telegram_id),
    )
    await start_profile_edit(stale_callback, state, user)

    foreign_callback = FakeCallbackQuery(
        data=f"profile:edit:age:{user.telegram_id}",
        message=current_editor,
        from_user=SimpleNamespace(id=9999),
    )
    await start_profile_edit(foreign_callback, state, user)

    assert stale_callback.answered == [
        {"text": PROFILE_EDITOR_UNAVAILABLE_TEXT, "show_alert": True}
    ]
    assert foreign_callback.answered == [
        {"text": PROFILE_EDITOR_UNAVAILABLE_TEXT, "show_alert": True}
    ]
    assert state.current_state is None


@pytest.mark.asyncio
async def test_two_users_can_edit_profile_without_cross_effects() -> None:
    first_state = FakeState()
    second_state = FakeState()
    bot = FakeBotApi()
    first_user = build_user(9, vip_active=False)
    second_user = build_user(10, vip_active=False)

    await show_profile(FakeMessage(bot=bot, chat_id=101, message_id=1, text="/profile"), first_state, first_user)
    await show_profile(FakeMessage(bot=bot, chat_id=202, message_id=2, text="/profile"), second_state, second_user)

    first_editor = bot.messages[first_state.data[PROFILE_EDITOR_MESSAGE_ID_KEY]]
    second_editor = bot.messages[second_state.data[PROFILE_EDITOR_MESSAGE_ID_KEY]]

    await start_profile_edit(
        FakeCallbackQuery(
            data=f"profile:edit:age:{first_user.telegram_id}",
            message=first_editor,
            from_user=SimpleNamespace(id=first_user.telegram_id),
        ),
        first_state,
        first_user,
    )

    assert first_editor.text == PROFILE_AGE_PROMPT_TEXT
    assert second_editor.text == PROFILE_EDITOR_HEADING_TEXT
    assert second_state.current_state is None

    service = FakeUserService()
    await update_age(
        FakeMessage(bot=bot, chat_id=101, message_id=3, text="29"),
        first_state,
        first_user,
        service,
    )

    assert "🎂 Age: 29" in bot.messages[first_state.data[PROFILE_CARD_MESSAGE_ID_KEY]].text
    assert bot.messages[second_state.data[PROFILE_CARD_MESSAGE_ID_KEY]].text == _profile_summary(second_user)
