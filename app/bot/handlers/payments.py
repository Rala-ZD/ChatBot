from __future__ import annotations

from aiogram import F, Router
from aiogram.enums import ChatType
from aiogram.types import CallbackQuery, Message, PreCheckoutQuery

from app.bot.keyboards.payments import points_package_keyboard, points_wallet_keyboard
from app.bot.keyboards.registration import preferred_gender_keyboard
from app.db.models.user import User
from app.services.payment_service import PaymentService
from app.services.user_service import UserService
from app.utils.text import (
    INVITE_UNAVAILABLE_TEXT,
    PAYMENTS_UNAVAILABLE_TEXT,
    build_buy_points_text,
    build_gender_selection_text,
    build_invite_text,
    build_points_purchase_success_text,
    build_points_status_text,
    build_vip_payment_success_text,
)

router = Router(name="payments")
router.message.filter(F.chat.type == ChatType.PRIVATE)
router.callback_query.filter(F.message.chat.type == ChatType.PRIVATE)


@router.callback_query(F.data == "payments:open")
async def open_buy_points(
    callback: CallbackQuery,
    app_user: User,
    user_service: UserService,
    payment_service: PaymentService,
) -> None:
    user_service.ensure_registered(app_user)
    if callback.message is None:
        await callback.answer()
        return

    if not payment_service.payments_enabled():
        await callback.answer("Unavailable", show_alert=True)
        await callback.message.answer(PAYMENTS_UNAVAILABLE_TEXT)
        return

    packages = payment_service.list_packages()
    await callback.message.edit_text(
        build_buy_points_text(app_user.points_balance, app_user.vip_until),
        reply_markup=points_package_keyboard(packages),
    )
    await callback.answer()


@router.callback_query(F.data == "payments:free")
async def open_free_points(
    callback: CallbackQuery,
    app_user: User,
    user_service: UserService,
) -> None:
    user_service.ensure_registered(app_user)
    if callback.message is None:
        await callback.answer()
        return

    bot = await callback.message.bot.get_me()
    if not bot.username:
        await callback.answer(INVITE_UNAVAILABLE_TEXT, show_alert=True)
        return

    await callback.message.answer(build_invite_text(bot.username, app_user.referral_code))
    await callback.answer()


@router.callback_query(F.data.startswith("payments:package:"))
async def send_points_invoice(
    callback: CallbackQuery,
    app_user: User,
    user_service: UserService,
    payment_service: PaymentService,
) -> None:
    user_service.ensure_registered(app_user)
    if callback.message is None:
        await callback.answer()
        return

    package_code = callback.data.rsplit(":", maxsplit=1)[-1]
    invoice = await payment_service.create_invoice_request(app_user, package_code)
    await callback.message.answer_invoice(
        title=invoice.title,
        description=invoice.description,
        payload=invoice.payload,
        currency=invoice.currency,
        prices=invoice.prices,
        start_parameter=invoice.start_parameter,
    )
    await callback.answer("Invoice sent")


@router.pre_checkout_query()
async def handle_pre_checkout(
    query: PreCheckoutQuery,
    payment_service: PaymentService,
) -> None:
    validation = await payment_service.validate_pre_checkout(query)
    await query.answer(ok=validation.ok, error_message=validation.error_message)


@router.message(F.successful_payment)
async def handle_successful_payment(
    message: Message,
    app_user: User,
    payment_service: PaymentService,
) -> None:
    if message.successful_payment is None:
        return

    result = await payment_service.finalize_successful_payment(app_user, message.successful_payment)
    if result.purchase_kind == "vip":
        if not result.already_processed:
            await message.answer(
                build_vip_payment_success_text(extended=result.vip_was_extended)
            )
        await message.answer(
            build_gender_selection_text(result.user.preferred_gender, result.user.vip_until),
            reply_markup=preferred_gender_keyboard(prefix="selectgender:set"),
        )
        return

    if result.already_processed:
        await message.answer(
            build_points_status_text(result.user.points_balance, result.user.vip_until),
            reply_markup=points_wallet_keyboard(),
        )
        return

    await message.answer(
        build_points_purchase_success_text(
            result.points_added,
            result.user.points_balance,
            result.user.vip_until,
        ),
        reply_markup=points_wallet_keyboard(),
    )
