from __future__ import annotations

from aiogram import F, Router
from aiogram.enums import ChatType
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from app.bot.keyboards.profile import profile_edit_keyboard
from app.bot.keyboards.registration import gender_keyboard, preferred_gender_keyboard
from app.bot.states.profile import ProfileStates
from app.db.models.user import User
from app.services.exceptions import ValidationError
from app.services.user_service import UserService
from app.utils.enums import Gender, PreferredGender
from app.utils.text import (
    format_interests,
    format_preferred_gender,
    format_premium_access_status,
)

router = Router(name="profile")
router.message.filter(F.chat.type == ChatType.PRIVATE)
router.callback_query.filter(F.message.chat.type == ChatType.PRIVATE)


@router.message(Command("profile"))
@router.message(F.text == "Profile")
async def show_profile(message: Message, app_user: User | None) -> None:
    if app_user is None or not app_user.is_registered:
        raise ValidationError("Finish setup with /start first.")
    await message.answer(_profile_summary(app_user), reply_markup=profile_edit_keyboard())


@router.callback_query(F.data.startswith("profile:edit:"))
async def start_profile_edit(callback: CallbackQuery, state: FSMContext, app_user: User | None) -> None:
    if app_user is None or not app_user.is_registered:
        raise ValidationError("Finish setup with /start first.")

    field = callback.data.rsplit(":", maxsplit=1)[-1]
    if field == "age":
        await state.set_state(ProfileStates.editing_age)
        await callback.message.answer("Enter your age.")
    elif field == "gender":
        await state.set_state(ProfileStates.editing_gender)
        await callback.message.answer(
            "Select your gender.",
            reply_markup=gender_keyboard(prefix="profile:gender"),
        )
    elif field == "nickname":
        await state.set_state(ProfileStates.editing_nickname)
        await callback.message.answer("Send a nickname, or `clear`.")
    elif field == "preferred_gender":
        await state.set_state(ProfileStates.editing_preferred_gender)
        await callback.message.answer(
            "Choose your filter.\nPremium matching only.",
            reply_markup=preferred_gender_keyboard(prefix="profile:preferred"),
        )
    elif field == "interests":
        await state.set_state(ProfileStates.editing_interests)
        await callback.message.answer("Send interests, or `clear`.")
    await callback.answer()


@router.message(ProfileStates.editing_age)
async def update_age(
    message: Message,
    state: FSMContext,
    app_user: User,
    user_service: UserService,
) -> None:
    age = user_service.parse_age(message.text or "")
    await user_service.update_profile(app_user, age=age)
    await state.clear()
    await message.answer(_profile_summary(app_user), reply_markup=profile_edit_keyboard())


@router.message(ProfileStates.editing_nickname)
async def update_nickname(
    message: Message,
    state: FSMContext,
    app_user: User,
    user_service: UserService,
) -> None:
    raw_value = (message.text or "").strip()
    nickname = None if raw_value.lower() in {"clear", "-"} else user_service.normalize_nickname(raw_value)
    await user_service.update_profile(app_user, nickname=nickname)
    await state.clear()
    await message.answer(_profile_summary(app_user), reply_markup=profile_edit_keyboard())


@router.message(ProfileStates.editing_interests)
async def update_interests(
    message: Message,
    state: FSMContext,
    app_user: User,
    user_service: UserService,
) -> None:
    raw_value = (message.text or "").strip()
    interests = [] if raw_value.lower() in {"clear", "-"} else user_service.normalize_interests(raw_value)
    await user_service.update_profile(app_user, interests_json=interests)
    await state.clear()
    await message.answer(_profile_summary(app_user), reply_markup=profile_edit_keyboard())


@router.callback_query(F.data.startswith("profile:gender:"), ProfileStates.editing_gender)
async def update_gender(
    callback: CallbackQuery,
    state: FSMContext,
    app_user: User,
    user_service: UserService,
) -> None:
    gender = Gender(callback.data.rsplit(":", maxsplit=1)[-1])
    await user_service.update_profile(app_user, gender=gender)
    await state.clear()
    await callback.message.answer(_profile_summary(app_user), reply_markup=profile_edit_keyboard())
    await callback.answer()


@router.callback_query(
    F.data.startswith("profile:preferred:"),
    ProfileStates.editing_preferred_gender,
)
async def update_preferred_gender(
    callback: CallbackQuery,
    state: FSMContext,
    app_user: User,
    user_service: UserService,
) -> None:
    preferred_gender = PreferredGender(callback.data.rsplit(":", maxsplit=1)[-1])
    await user_service.update_profile(app_user, preferred_gender=preferred_gender)
    await state.clear()
    await callback.message.answer(_profile_summary(app_user), reply_markup=profile_edit_keyboard())
    await callback.answer()


def _profile_summary(user: User) -> str:
    return (
        "\U0001f464 Profile\n\n"
        f"Age: {user.age or 'Not set'}\n"
        f"Gender: {user.gender.value.title() if user.gender else 'Not set'}\n"
        f"Nick: {user.nickname or 'Not set'}\n"
        f"Filter: {format_preferred_gender(user.preferred_gender)}\n"
        f"Premium: {format_premium_access_status(user.vip_until)}\n"
        f"Interests: {format_interests(user.interests_json)}"
    )
