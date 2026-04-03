from __future__ import annotations

from aiogram import F, Router
from aiogram.enums import ChatType
from aiogram.types import Message

from app.bot.keyboards.common import searching_keyboard
from app.db.models.user import User
from app.schemas.common import MatchOutcome
from app.services.match_service import MatchService
from app.utils.text import SEARCHING_TEXT

router = Router(name="matchmaking")
router.message.filter(F.chat.type == ChatType.PRIVATE)


@router.message(F.text == "Start Chat")
async def start_chat(message: Message, app_user: User, match_service: MatchService) -> None:
    await start_chat_flow(message, app_user, match_service)


async def start_chat_flow(message: Message, app_user: User, match_service: MatchService) -> None:
    outcome = await match_service.start(app_user)
    await _respond_to_match_outcome(message, outcome)


async def _respond_to_match_outcome(message: Message, outcome: MatchOutcome) -> None:
    if outcome.status == "matched":
        return
    await message.answer(SEARCHING_TEXT, reply_markup=searching_keyboard())
