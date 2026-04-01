from __future__ import annotations

from aiogram import F, Router
from aiogram.enums import ChatType
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message

from app.bot.keyboards.premium import premium_points_exchange_keyboard
from app.db.models.user import User
from app.services.exceptions import ValidationError
from app.services.user_service import UserService
from app.utils.text import (
    INVITE_UNAVAILABLE_TEXT,
    VIP_POINTS_REQUIRED_TEXT,
    build_referral_premium_text,
    build_vip_unlocked_text,
)

router = Router(name="referral")
router.message.filter(F.chat.type == ChatType.PRIVATE)
router.callback_query.filter(F.message.chat.type == ChatType.PRIVATE)


async def _build_referral_summary(
    message: Message,
    app_user: User,
    user_service: UserService,
) -> str | None:
    bot = await message.bot.get_me()
    if not bot.username:
        return None

    referral_count = await user_service.count_registered_referrals(app_user)
    return build_referral_premium_text(
        bot.username,
        app_user.referral_code,
        app_user.points_balance,
        referral_count,
    )


@router.message(Command("invite"))
async def invite_handler(message: Message, app_user: User, user_service: UserService) -> None:
    user_service.ensure_registered(app_user)
    summary = await _build_referral_summary(message, app_user, user_service)
    if summary is None:
        await message.answer(INVITE_UNAVAILABLE_TEXT)
        return

    await message.answer(summary)


@router.message(Command("points"))
async def points_handler(message: Message, app_user: User, user_service: UserService) -> None:
    user_service.ensure_registered(app_user)
    summary = await _build_referral_summary(message, app_user, user_service)
    if summary is None:
        await message.answer(INVITE_UNAVAILABLE_TEXT)
        return

    await message.answer(
        summary,
        reply_markup=premium_points_exchange_keyboard(),
    )


@router.message(Command("vip"))
async def vip_handler(message: Message, app_user: User, user_service: UserService) -> None:
    user_service.ensure_registered(app_user)
    try:
        updated_user = await user_service.purchase_vip(app_user)
    except ValidationError:
        await message.answer(VIP_POINTS_REQUIRED_TEXT)
        return

    await message.answer(
        build_vip_unlocked_text(updated_user.points_balance, updated_user.vip_until)
    )


@router.callback_query(F.data == "referral:exchange")
async def exchange_points_from_referral_tab(
    callback: CallbackQuery,
    app_user: User,
    user_service: UserService,
) -> None:
    user_service.ensure_registered(app_user)
    if callback.message is None:
        await callback.answer()
        return

    try:
        updated_user = await user_service.purchase_vip(app_user)
    except ValidationError as exc:
        await callback.answer(str(exc), show_alert=True)
        return

    await callback.message.edit_text(
        build_vip_unlocked_text(updated_user.points_balance, updated_user.vip_until),
        reply_markup=None,
    )
    await callback.answer()
