from __future__ import annotations

from aiogram import F, Router
from aiogram.enums import ChatType
from aiogram.filters import Command
from aiogram.types import Message

from app.bot.keyboards.payments import points_wallet_keyboard
from app.db.models.user import User
from app.services.exceptions import ValidationError
from app.services.user_service import UserService
from app.utils.text import (
    INVITE_UNAVAILABLE_TEXT,
    VIP_POINTS_REQUIRED_TEXT,
    build_invite_text,
    build_points_status_text,
    build_vip_unlocked_text,
)

router = Router(name="referral")
router.message.filter(F.chat.type == ChatType.PRIVATE)


@router.message(Command("invite"))
async def invite_handler(message: Message, app_user: User, user_service: UserService) -> None:
    user_service.ensure_registered(app_user)
    bot = await message.bot.get_me()
    if not bot.username:
        await message.answer(INVITE_UNAVAILABLE_TEXT)
        return

    await message.answer(build_invite_text(bot.username, app_user.referral_code))


@router.message(Command("points"))
async def points_handler(message: Message, app_user: User, user_service: UserService) -> None:
    user_service.ensure_registered(app_user)
    await message.answer(
        build_points_status_text(app_user.points_balance, app_user.vip_until),
        reply_markup=points_wallet_keyboard(),
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
