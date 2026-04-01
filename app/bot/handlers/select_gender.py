from __future__ import annotations

from aiogram import F, Router
from aiogram.enums import ChatType
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message

from app.bot.keyboards.premium import (
    premium_gender_gate_keyboard,
    premium_gender_referral_keyboard,
)
from app.bot.keyboards.registration import preferred_gender_keyboard
from app.db.models.user import User
from app.services.exceptions import ValidationError
from app.services.user_service import UserService
from app.utils.enums import PreferredGender
from app.utils.text import (
    INVITE_UNAVAILABLE_TEXT,
    RETURNING_HOME_TEXT,
    SELECT_GENDER_BUTTON_TEXT,
    build_gender_selection_text,
    build_premium_gender_gate_text,
    build_referral_premium_text,
)

router = Router(name="select_gender")
router.message.filter(F.chat.type == ChatType.PRIVATE)
router.callback_query.filter(F.message.chat.type == ChatType.PRIVATE)


async def _build_referral_premium_view(
    message: Message,
    app_user: User,
    user_service: UserService,
) -> tuple[str, object] | None:
    bot = await message.bot.get_me()
    if not bot.username:
        return None

    referral_count = await user_service.count_registered_referrals(app_user)
    return (
        build_referral_premium_text(
            bot.username,
            app_user.referral_code,
            app_user.points_balance,
            referral_count,
        ),
        premium_gender_referral_keyboard(),
    )


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
        build_premium_gender_gate_text(),
        reply_markup=premium_gender_gate_keyboard(),
    )


@router.callback_query(F.data.startswith("selectgender:plan:"))
async def preview_vip_plan(
    callback: CallbackQuery,
    app_user: User,
    user_service: UserService,
) -> None:
    user_service.ensure_registered(app_user)
    if callback.message is None:
        await callback.answer()
        return

    await callback.message.edit_text(
        build_premium_gender_gate_text(),
        reply_markup=premium_gender_gate_keyboard(),
    )
    await callback.answer("Invite 3 friends to unlock 6 hours of premium", show_alert=True)


@router.callback_query(F.data == "selectgender:referral:wallet")
async def handle_legacy_referral_wallet_callback(
    callback: CallbackQuery,
    app_user: User,
    user_service: UserService,
) -> None:
    user_service.ensure_registered(app_user)
    if callback.message is None:
        await callback.answer()
        return

    referral_view = await _build_referral_premium_view(callback.message, app_user, user_service)
    if referral_view is None:
        await callback.answer(INVITE_UNAVAILABLE_TEXT, show_alert=True)
        return

    text, reply_markup = referral_view
    await callback.message.edit_text(
        text,
        reply_markup=reply_markup,
    )
    await callback.answer("Use referrals to earn premium now", show_alert=True)


@router.callback_query(F.data == "selectgender:free")
async def open_select_gender_referral(
    callback: CallbackQuery,
    app_user: User,
    user_service: UserService,
) -> None:
    user_service.ensure_registered(app_user)
    if callback.message is None:
        await callback.answer()
        return

    referral_view = await _build_referral_premium_view(callback.message, app_user, user_service)
    if referral_view is None:
        await callback.answer(INVITE_UNAVAILABLE_TEXT, show_alert=True)
        return

    text, reply_markup = referral_view
    await callback.message.edit_text(
        text,
        reply_markup=reply_markup,
    )
    await callback.answer()


@router.callback_query(F.data == "selectgender:referral:exchange")
async def exchange_points_for_select_gender_premium(
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
        build_gender_selection_text(
            updated_user.preferred_gender,
            updated_user.vip_until,
            success=True,
        ),
        reply_markup=preferred_gender_keyboard(prefix="selectgender:set"),
    )
    await callback.answer()


@router.callback_query(F.data == "selectgender:back")
async def close_select_gender_gate(
    callback: CallbackQuery,
    app_user: User,
    user_service: UserService,
) -> None:
    user_service.ensure_registered(app_user)
    if callback.message is None:
        await callback.answer()
        return

    await callback.message.edit_text(RETURNING_HOME_TEXT, reply_markup=None)
    await callback.answer()


@router.callback_query(F.data == "selectgender:referral:back")
async def return_to_select_gender_gate(
    callback: CallbackQuery,
    app_user: User,
    user_service: UserService,
) -> None:
    user_service.ensure_registered(app_user)
    if callback.message is None:
        await callback.answer()
        return

    await callback.message.edit_text(
        build_premium_gender_gate_text(),
        reply_markup=premium_gender_gate_keyboard(),
    )
    await callback.answer()


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
            build_premium_gender_gate_text(),
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
