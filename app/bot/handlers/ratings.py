from __future__ import annotations

from aiogram import F, Router
from aiogram.enums import ChatType
from aiogram.exceptions import TelegramBadRequest
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery

from app.bot.keyboards.chat import chat_summary_keyboard
from app.bot.states.report import ReportStates
from app.db.models.user import User
from app.services.exceptions import AccessDeniedError, ConflictError, NotFoundError
from app.services.rating_service import RatingService
from app.services.session_service import SessionService
from app.utils.enums import SessionRatingValue, SessionStatus
from app.utils.text import (
    CHAT_UNAVAILABLE_TEXT,
    FEEDBACK_SAVED_TEXT,
    REPORT_PROMPT_TEXT,
)

router = Router(name="ratings")
router.callback_query.filter(F.message.chat.type == ChatType.PRIVATE)


@router.callback_query(F.data.startswith("chatrate:good:"))
async def rate_chat_good(
    callback: CallbackQuery,
    app_user: User,
    rating_service: RatingService,
) -> None:
    await _save_rating(callback, app_user.id, SessionRatingValue.GOOD, rating_service)


@router.callback_query(F.data.startswith("chatrate:bad:"))
async def rate_chat_bad(
    callback: CallbackQuery,
    app_user: User,
    rating_service: RatingService,
) -> None:
    await _save_rating(callback, app_user.id, SessionRatingValue.BAD, rating_service)


@router.callback_query(F.data.startswith("chatrate:report:"))
async def report_from_summary(
    callback: CallbackQuery,
    state: FSMContext,
    app_user: User,
    session_service: SessionService,
) -> None:
    session_id = _parse_session_id(callback.data)
    if session_id is None:
        await _answer_chat_unavailable(callback)
        return

    chat_session = await session_service.get_session_for_user(session_id, app_user.id)
    if (
        chat_session is None
        or chat_session.status != SessionStatus.ENDED
        or chat_session.ended_at is None
    ):
        await _answer_chat_unavailable(callback)
        return
    await state.set_state(ReportStates.awaiting_reason)
    await state.update_data(session_id=session_id)
    await callback.answer()
    if callback.message is not None:
        await callback.message.answer(REPORT_PROMPT_TEXT)


async def _save_rating(
    callback: CallbackQuery,
    from_user_id: int,
    value: SessionRatingValue,
    rating_service: RatingService,
) -> None:
    session_id = _parse_session_id(callback.data)
    if session_id is None:
        await _answer_chat_unavailable(callback)
        return

    try:
        result = await rating_service.save_rating(session_id, from_user_id, value)
    except (AccessDeniedError, ConflictError, NotFoundError):
        await _answer_chat_unavailable(callback)
        return

    if result.already_saved:
        await _answer_chat_unavailable(callback)
        return

    if callback.message is not None:
        try:
            await callback.message.edit_reply_markup(
                reply_markup=chat_summary_keyboard(session_id, allow_rating=False),
            )
        except TelegramBadRequest:
            pass
    await callback.answer(FEEDBACK_SAVED_TEXT)


async def _answer_chat_unavailable(callback: CallbackQuery) -> None:
    await callback.answer(CHAT_UNAVAILABLE_TEXT, show_alert=True)
    if callback.message is None:
        return
    try:
        await callback.message.edit_reply_markup(reply_markup=None)
    except TelegramBadRequest:
        pass


def _parse_session_id(data: str | None) -> int | None:
    if data is None:
        return None
    try:
        return int(data.rsplit(":", maxsplit=1)[-1])
    except (TypeError, ValueError):
        return None
