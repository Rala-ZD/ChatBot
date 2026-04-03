from __future__ import annotations

from aiogram import Bot
from aiogram.types import BotCommand


def build_bot_commands() -> list[BotCommand]:
    return [
        BotCommand(command="start", description="Start chat"),
        BotCommand(command="next", description="Next match"),
        BotCommand(command="end", description="End chat"),
        BotCommand(command="cancel", description="Cancel current step or search"),
        BotCommand(command="profile", description="Edit your profile"),
        BotCommand(command="help", description="Help"),
        BotCommand(command="rules", description="Safety rules"),
        BotCommand(command="report", description="Report chat"),
    ]


async def register_bot_commands(bot: Bot) -> None:
    await bot.set_my_commands(build_bot_commands())
