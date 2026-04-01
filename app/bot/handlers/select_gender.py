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
from app.services.payment_service import PaymentService
from app.services.user_service import UserService
from app.utils.enums import PreferredGender
from app.utils.text import (
    INVITE_UNAVAILABLE_TEXT,
    PREMIUM_SCREEN_UNAVAILABLE_TEXT,
    RETURNING_HOME_TEXT,
    SELECT_GENDER_BUTTON_TEXT,
    VIP_CHECKOUT_COMING_SOON_TEXT,
    build_gender_selection_text,
    build_premium_gender_gate_text,
    build_referral_premium_text,
)

router = Router(name="select_gender")
router.message.filter(F.chat.type == ChatType.PRIVATE)
router.callback_query.filter(F.message.chat.type == ChatType.PRIVATE)


def _extract_owner_telegram_id(data: str | None) -> int | None:
    if data is None:
        return None
    try:
        return int(data.rsplit(":", maxsplit=1)[-1])
    except (TypeError, ValueError):
        return None


async def _ensure_callback_owner(callback: CallbackQuery, app_user: User) -> bool:
    owner_telegram_id = _extract_owner_telegram_id(callback.data)
    from_user = callback.from_user
    if (
        from_user is None
        or owner_telegram_id is None
        or from_user.id != owner_telegram_id
        or app_user.telegram_id != from_user.id
    ):
        await callback.answer(PREMIUM_SCREEN_UNAVAILABLE_TEXT, show_alert=True)
        return False
    return True


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
        premium_gender_referral_keyboard(app_user.telegram_id),
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
        reply_markup=premium_gender_gate_keyboard(app_user.telegram_id),
    )


@router.callback_query(F.data.startswith("selectgender:plan:"))
async def preview_vip_plan(
    callback: CallbackQuery,
    app_user: User,
    user_service: UserService,
    payment_service: PaymentService,
) -> None:
    if not await _ensure_callback_owner(callback, app_user):
        return
    user_service.ensure_registered(app_user)
    if callback.message is None:
        await callback.answer()
        return

    plan_key = callback.data.rsplit(":", maxsplit=2)[-2]
    plan_codes = {
        "week": "vip_week",
        "month": "vip_month",
        "6months": "vip_6months",
    }
    plan_code = plan_codes.get(plan_key)
    if plan_code is None:
        await callback.answer(VIP_CHECKOUT_COMING_SOON_TEXT, show_alert=True)
        return

    try:
        invoice = await payment_service.create_invoice_request(app_user, plan_code)
    except ValidationError:
        await callback.answer(VIP_CHECKOUT_COMING_SOON_TEXT, show_alert=True)
        return

    await callback.message.answer_invoice(
        title=invoice.title,
        description=invoice.description,
        payload=invoice.payload,
        currency=invoice.currency,
        prices=invoice.prices,
        start_parameter=invoice.start_parameter,
    )
    await callback.answer("Invoice sent")


@router.callback_query(F.data == "selectgender:referral:wallet")
async def handle_legacy_referral_wallet_callback(
    callback: CallbackQuery,
    app_user: User,
    user_service: UserService,
) -> None:
    user_service.ensure_registered(app_user)
    await callback.answer(PREMIUM_SCREEN_UNAVAILABLE_TEXT, show_alert=True)


@router.callback_query(F.data.startswith("selectgender:free"))
async def open_select_gender_referral(
    callback: CallbackQuery,
    app_user: User,
    user_service: UserService,
) -> None:
    if not await _ensure_callback_owner(callback, app_user):
        return
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


@router.callback_query(F.data.startswith("selectgender:referral:exchange"))
async def exchange_points_for_select_gender_premium(
    callback: CallbackQuery,
    app_user: User,
    user_service: UserService,
) -> None:
    if not await _ensure_callback_owner(callback, app_user):
        return
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


@router.callback_query(F.data.startswith("selectgender:back"))
async def close_select_gender_gate(
    callback: CallbackQuery,
    app_user: User,
    user_service: UserService,
) -> None:
    if not await _ensure_callback_owner(callback, app_user):
        return
    user_service.ensure_registered(app_user)
    if callback.message is None:
        await callback.answer()
        return

    await callback.message.edit_text(RETURNING_HOME_TEXT, reply_markup=None)
    await callback.answer()


@router.callback_query(F.data.startswith("selectgender:referral:back"))
async def return_to_select_gender_gate(
    callback: CallbackQuery,
    app_user: User,
    user_service: UserService,
) -> None:
    if not await _ensure_callback_owner(callback, app_user):
        return
    user_service.ensure_registered(app_user)
    if callback.message is None:
        await callback.answer()
        return

    await callback.message.edit_text(
        build_premium_gender_gate_text(),
        reply_markup=premium_gender_gate_keyboard(app_user.telegram_id),
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
            reply_markup=premium_gender_gate_keyboard(app_user.telegram_id),
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
