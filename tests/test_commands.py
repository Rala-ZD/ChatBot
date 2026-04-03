from __future__ import annotations

from dataclasses import dataclass, field

import pytest

from app.bot.commands import build_bot_commands
from app.bot.handlers.menu import rules_message
from app.bot.keyboards.common import main_menu_keyboard
from app.utils.text import RULES_TEXT


def _reply_keyboard_texts(markup) -> list[str]:
    if markup is None:
        return []
    return [button.text for row in markup.keyboard for button in row]


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


def test_build_bot_commands_uses_expected_order_and_descriptions() -> None:
    commands = build_bot_commands()

    assert [(command.command, command.description) for command in commands] == [
        ("start", "Start chat"),
        ("next", "Next match"),
        ("end", "End chat"),
        ("cancel", "Cancel current step or search"),
        ("profile", "Edit your profile"),
        ("help", "Help"),
        ("rules", "Safety rules"),
        ("report", "Report chat"),
    ]


@pytest.mark.asyncio
async def test_rules_command_uses_same_safety_output_as_button() -> None:
    message = FakeMessage(text="/rules")

    await rules_message(message)

    assert message.answers[-1].text == RULES_TEXT
    assert _reply_keyboard_texts(message.answers[-1].reply_markup) == _reply_keyboard_texts(
        main_menu_keyboard()
    )
