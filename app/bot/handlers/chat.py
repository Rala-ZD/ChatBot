from __future__ import annotations

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from app.bot.keyboards.callbacks import ReportCallback
from app.bot.keyboards.menus import (
    chat_menu_keyboard,
    main_menu_keyboard,
    report_note_keyboard,
    report_reasons_keyboard,
    waiting_menu_keyboard,
)
from app.bot.states.report import ReportStates
from app.db.models import ReportReason, SessionEndReason
from app.services.container import ServiceContainer
from app.utils.constants import (
    CHAT_MENU_END,
    CHAT_MENU_NEXT,
    CHAT_MENU_REPORT,
    MAIN_MENU_START_CHAT,
    WAITING_MENU_CANCEL,
)

router = Router(name="chat")


@router.message(F.text == MAIN_MENU_START_CHAT)
async def start_chat(
    message: Message,
    services: ServiceContainer,
) -> None:
    await services.user_service.sync_telegram_user(message.from_user)
    result = await services.match_service.enqueue_user(message.from_user)
    if result.waiting:
        await message.answer(
            "Searching for a stranger. You can cancel while waiting.",
            reply_markup=waiting_menu_keyboard(),
        )
        return
    await message.answer(
        "You are now in an anonymous chat.",
        reply_markup=chat_menu_keyboard(),
    )


@router.message(Command("next"))
@router.message(F.text == CHAT_MENU_NEXT)
async def next_stranger(
    message: Message,
    services: ServiceContainer,
) -> None:
    end_result = await services.session_service.end_active_session_by_telegram_id(
        message.from_user.id,
        SessionEndReason.NEXT,
    )
    if not end_result.ended:
        await message.answer("You are not currently in a chat.", reply_markup=main_menu_keyboard())
        return

    result = await services.match_service.enqueue_user(message.from_user)
    if result.waiting:
        await message.answer(
            "Searching for a new stranger...",
            reply_markup=waiting_menu_keyboard(),
        )
    else:
        await message.answer("Connected to a new stranger.", reply_markup=chat_menu_keyboard())


@router.message(Command("end"))
@router.message(F.text == CHAT_MENU_END)
async def end_chat(
    message: Message,
    services: ServiceContainer,
) -> None:
    end_result = await services.session_service.end_active_session_by_telegram_id(
        message.from_user.id,
        SessionEndReason.USER_END,
    )
    if not end_result.ended:
        await message.answer("You are not currently in a chat.", reply_markup=main_menu_keyboard())
        return
    await message.answer("Back at the main menu.", reply_markup=main_menu_keyboard())


@router.message(Command("report"))
@router.message(F.text == CHAT_MENU_REPORT)
async def report_user(
    message: Message,
    state: FSMContext,
    services: ServiceContainer,
) -> None:
    context = await services.session_service.get_active_context_by_telegram_id(message.from_user.id)
    if context is None:
        await message.answer("You can only report a user during an active chat.", reply_markup=main_menu_keyboard())
        return
    await state.set_state(ReportStates.reason)
    await message.answer(
        "Choose a reason for the report.",
        reply_markup=report_reasons_keyboard(),
    )


@router.callback_query(
    ReportStates.reason,
    ReportCallback.filter(F.action == "reason"),
)
async def report_reason_selected(
    callback: CallbackQuery,
    state: FSMContext,
) -> None:
    reason = ReportCallback.unpack(callback.data).value
    await state.update_data(reason=reason)
    await state.set_state(ReportStates.note)
    await callback.message.edit_text(
        "Add an optional note for the moderators, or skip it.",
        reply_markup=report_note_keyboard(),
    )
    await callback.answer()


@router.message(ReportStates.note)
async def report_note_submitted(
    message: Message,
    state: FSMContext,
    services: ServiceContainer,
) -> None:
    data = await state.get_data()
    await services.moderation_service.submit_report(
        message.from_user.id,
        reason=ReportReason(data["reason"]),
        note=message.text or None,
    )
    await state.clear()
    await message.answer(
        "The report has been sent and the chat was closed.",
        reply_markup=main_menu_keyboard(),
    )


@router.callback_query(
    ReportStates.note,
    ReportCallback.filter(F.action == "note", F.value == "skip"),
)
async def report_note_skipped(
    callback: CallbackQuery,
    state: FSMContext,
    services: ServiceContainer,
) -> None:
    data = await state.get_data()
    await services.moderation_service.submit_report(
        callback.from_user.id,
        reason=ReportReason(data["reason"]),
        note=None,
    )
    await state.clear()
    await callback.message.answer(
        "The report has been sent and the chat was closed.",
        reply_markup=main_menu_keyboard(),
    )
    await callback.answer()


@router.message(F.text == WAITING_MENU_CANCEL)
async def cancel_waiting(
    message: Message,
    services: ServiceContainer,
) -> None:
    cancelled = await services.match_service.cancel_waiting(message.from_user.id)
    if cancelled:
        await message.answer("Search cancelled.", reply_markup=main_menu_keyboard())
        return
    await message.answer("You are not currently waiting for a match.", reply_markup=main_menu_keyboard())


@router.message()
async def relay_or_fallback(
    message: Message,
    services: ServiceContainer,
) -> None:
    handled = await services.relay_service.relay_message(message)
    if handled:
        return

    if await services.match_service.is_waiting(message.from_user.id):
        await message.answer(
            "Still searching for a stranger. Use Cancel Search if you want to stop.",
            reply_markup=waiting_menu_keyboard(),
        )
        return

    user = await services.user_service.get_by_telegram_id(message.from_user.id)
    if user and user.is_registered:
        await message.answer(
            "Use Start Chat when you are ready to meet someone new.",
            reply_markup=main_menu_keyboard(),
        )
        return

    await message.answer(
        "Use /start to begin registration before chatting.",
        reply_markup=main_menu_keyboard(),
    )
