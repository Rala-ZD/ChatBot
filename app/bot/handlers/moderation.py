from __future__ import annotations

from aiogram import F, Router
from aiogram.enums import ChatType
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import Message

from app.bot.keyboards.common import main_menu_keyboard
from app.bot.states.report import ReportStates
from app.db.models.user import User
from app.services.exceptions import ConflictError
from app.services.moderation_service import ModerationService
from app.services.session_service import SessionService
from app.utils.enums import EndReason
from app.utils.text import REPORT_DONE_TEXT, REPORT_PROMPT_TEXT

router = Router(name="moderation")
router.message.filter(F.chat.type == ChatType.PRIVATE)


@router.message(Command("report"))
@router.message(F.text == "Report")
async def start_report(
    message: Message,
    state: FSMContext,
    app_user: User,
    session_service: SessionService,
) -> None:
    active_session = await session_service.get_active_session_for_user(app_user.id)
    if active_session is None:
        raise ConflictError("You can only send a report while you're in a chat.")
    await state.set_state(ReportStates.awaiting_reason)
    await state.update_data(session_id=active_session.id)
    await message.answer(REPORT_PROMPT_TEXT)


@router.message(ReportStates.awaiting_reason)
async def submit_report(
    message: Message,
    state: FSMContext,
    app_user: User,
    moderation_service: ModerationService,
    session_service: SessionService,
) -> None:
    data = await state.get_data()
    session_id = int(data["session_id"])
    chat_session = await session_service.session_repository.get_with_details(session_id)
    if chat_session is None:
        raise ConflictError("The chat is no longer active.")

    await moderation_service.create_report(chat_session, app_user, message.text or "")
    await session_service.end_session(
        chat_session.id,
        EndReason.REPORT,
        ended_by_user_id=app_user.id,
    )
    await state.clear()
    await message.answer(
        REPORT_DONE_TEXT,
        reply_markup=main_menu_keyboard(),
    )
