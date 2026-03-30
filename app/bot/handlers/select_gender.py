from __future__ import annotations

from aiogram import F, Router
from aiogram.enums import ChatType
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message

from app.bot.keyboards.premium import premium_gender_gate_keyboard
from app.bot.keyboards.registration import preferred_gender_keyboard
from app.db.models.user import User
from app.services.exceptions import ValidationError
from app.services.user_service import VIP_COST_POINTS, UserService
from app.utils.enums import PreferredGender
from app.utils.text import (
    SELECT_GENDER_BUTTON_TEXT,
    build_gender_selection_text,
    build_premium_gender_gate_text,
)

router = Router(name="select_gender")
router.message.filter(F.chat.type == ChatType.PRIVATE)
router.callback_query.filter(F.message.chat.type == ChatType.PRIVATE)


@router.message(Command("selectgender"))
@router.message(F.text == SELECT_GENDER_BUTTON_TEXT)
async def open_select_gender(message: Message, app_user: User, user_service: UserService) -> None:
    user_service.ensure_registered(app_user)
    if app_user.has_active_vip():
        await message.answer(
            build_gender_selection_text(app_user.preferred_gender, app_user.vip_until),
            reply_markup=preferred_gender_keyboard(prefix="selectgender:set"),
        )
        return

    await message.answer(
        build_premium_gender_gate_text(app_user.points_balance, VIP_COST_POINTS),
        reply_markup=premium_gender_gate_keyboard(),
    )


@router.callback_query(F.data == "selectgender:unlock")
async def unlock_select_gender(
    callback: CallbackQuery,
    app_user: User,
    user_service: UserService,
) -> None:
    user_service.ensure_registered(app_user)
    if callback.message is None:
        await callback.answer()
        return

    if app_user.has_active_vip():
        await callback.message.edit_text(
            build_gender_selection_text(app_user.preferred_gender, app_user.vip_until),
            reply_markup=preferred_gender_keyboard(prefix="selectgender:set"),
        )
        await callback.answer("Active")
        return

    try:
        updated_user = await user_service.purchase_vip(app_user)
    except ValidationError as e:
       await callback.answer(str(e), show_alert=True)
       return

    await callback.message.edit_text(
        build_gender_selection_text(
            updated_user.preferred_gender,
            updated_user.vip_until,
            success=True,
        ),
        reply_markup=preferred_gender_keyboard(prefix="selectgender:set"),
    )
    await callback.answer("Unlocked")


@router.callback_query(F.data.startswith("selectgender:set:"))
async def set_preferred_gender_from_premium_flow(
    callback: CallbackQuery,
    app_user: User,
    user_service: UserService,
) -> None:
    user_service.ensure_registered(app_user)
    if callback.message is None:
        await callback.answer()
        return

    if not app_user.has_active_vip():
        await callback.message.edit_text(
            build_premium_gender_gate_text(app_user.points_balance, VIP_COST_POINTS),
            reply_markup=premium_gender_gate_keyboard(),
        )
        await callback.answer("Premium required", show_alert=True)
        return

    selected_value = callback.data.rsplit(":", maxsplit=1)[-1]
    preferred_gender = PreferredGender(selected_value)
    updated_user = await user_service.update_profile(app_user, preferred_gender=preferred_gender)

    await callback.message.edit_text(
        build_gender_selection_text(updated_user.preferred_gender, updated_user.vip_until),
        reply_markup=preferred_gender_keyboard(prefix="selectgender:set"),
    )
    await callback.answer("Updated")
