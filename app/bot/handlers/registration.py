from __future__ import annotations

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from app.bot.keyboards.callbacks import ProfileCallback, RegistrationCallback
from app.bot.keyboards.menus import (
    consent_keyboard,
    gender_keyboard,
    main_menu_keyboard,
    preferred_gender_keyboard,
    profile_keyboard,
    registration_start_keyboard,
    skip_keyboard,
)
from app.bot.states.registration import ProfileEditStates, RegistrationStates
from app.db.models import Gender, PreferredGender
from app.services.container import ServiceContainer
from app.utils.exceptions import UserVisibleError

router = Router(name="registration")


@router.callback_query(RegistrationCallback.filter(F.action == "begin"))
async def begin_registration(
    callback: CallbackQuery,
    state: FSMContext,
    services: ServiceContainer,
) -> None:
    await services.user_service.sync_telegram_user(callback.from_user)
    await state.clear()
    await state.set_state(RegistrationStates.age)
    await callback.message.edit_text(
        "First, how old are you?\nSend your age as a number.",
    )
    await callback.answer()


@router.message(RegistrationStates.age)
async def registration_age(
    message: Message,
    state: FSMContext,
    services: ServiceContainer,
) -> None:
    age = services.user_service.validate_age(message.text or "")
    await state.update_data(age=age)
    await state.set_state(RegistrationStates.gender)
    await message.answer("Choose your gender.", reply_markup=gender_keyboard())


@router.callback_query(
    RegistrationStates.gender,
    RegistrationCallback.filter(F.action == "gender"),
)
async def registration_gender(
    callback: CallbackQuery,
    state: FSMContext,
) -> None:
    await state.update_data(gender=callback.data.split(":")[-1])
    await state.set_state(RegistrationStates.nickname)
    await callback.message.edit_text(
        "Set an optional nickname, or skip this step.",
        reply_markup=skip_keyboard("nickname"),
    )
    await callback.answer()


@router.message(RegistrationStates.nickname)
async def registration_nickname(
    message: Message,
    state: FSMContext,
    services: ServiceContainer,
) -> None:
    nickname = services.user_service.validate_nickname(message.text or "")
    await state.update_data(nickname=nickname)
    await state.set_state(RegistrationStates.preferred_gender)
    await message.answer(
        "Do you have a preferred gender for matches? You can also skip.",
        reply_markup=preferred_gender_keyboard(),
    )


@router.callback_query(
    RegistrationStates.nickname,
    RegistrationCallback.filter(F.action == "nickname", F.value == "skip"),
)
async def registration_nickname_skip(
    callback: CallbackQuery,
    state: FSMContext,
) -> None:
    await state.update_data(nickname=None)
    await state.set_state(RegistrationStates.preferred_gender)
    await callback.message.edit_text(
        "Do you have a preferred gender for matches? You can also skip.",
        reply_markup=preferred_gender_keyboard(),
    )
    await callback.answer()


@router.callback_query(
    RegistrationStates.preferred_gender,
    RegistrationCallback.filter(F.action == "preferred_gender"),
)
async def registration_preferred_gender(
    callback: CallbackQuery,
    state: FSMContext,
) -> None:
    value = callback.data.split(":")[-1]
    preferred_gender = None if value == "skip" else value
    await state.update_data(preferred_gender=preferred_gender)
    await state.set_state(RegistrationStates.interests)
    await callback.message.edit_text(
        "Add optional interests separated by commas, or skip.",
        reply_markup=skip_keyboard("interests"),
    )
    await callback.answer()


@router.message(RegistrationStates.interests)
async def registration_interests(
    message: Message,
    state: FSMContext,
    services: ServiceContainer,
) -> None:
    interests = services.user_service.validate_interests(message.text or "")
    await state.update_data(interests=interests)
    await state.set_state(RegistrationStates.consent)
    await message.answer(
        "Please review the rules and confirm that you agree to use the bot safely.",
        reply_markup=consent_keyboard(),
    )


@router.callback_query(
    RegistrationStates.interests,
    RegistrationCallback.filter(F.action == "interests", F.value == "skip"),
)
async def registration_interests_skip(
    callback: CallbackQuery,
    state: FSMContext,
) -> None:
    await state.update_data(interests=[])
    await state.set_state(RegistrationStates.consent)
    await callback.message.edit_text(
        "Please review the rules and confirm that you agree to use the bot safely.",
        reply_markup=consent_keyboard(),
    )
    await callback.answer()


@router.callback_query(
    RegistrationStates.consent,
    RegistrationCallback.filter(F.action == "consent", F.value == "accept"),
)
async def registration_complete(
    callback: CallbackQuery,
    state: FSMContext,
    services: ServiceContainer,
) -> None:
    data = await state.get_data()
    gender = Gender(data["gender"])
    preferred_gender = (
        PreferredGender(data["preferred_gender"])
        if data.get("preferred_gender")
        else None
    )
    user = await services.user_service.complete_registration(
        callback.from_user,
        age=data["age"],
        gender=gender,
        nickname=data.get("nickname"),
        preferred_gender=preferred_gender,
        interests=data.get("interests", []),
    )
    await state.clear()
    await callback.message.edit_text(
        "Registration complete. You can now start anonymous chats.",
    )
    await callback.message.answer(
        services.user_service.format_profile(user),
        reply_markup=main_menu_keyboard(),
    )
    await callback.answer()


@router.callback_query(ProfileCallback.filter())
async def begin_profile_edit(
    callback: CallbackQuery,
    state: FSMContext,
    services: ServiceContainer,
) -> None:
    user = await services.user_service.require_registered_user(callback.from_user.id)
    field = ProfileCallback.unpack(callback.data).field
    await state.clear()

    if field == "age":
        await state.set_state(ProfileEditStates.age)
        await callback.message.answer("Send your new age.")
    elif field == "gender":
        await state.set_state(ProfileEditStates.gender)
        await callback.message.answer("Choose your new gender.", reply_markup=gender_keyboard())
    elif field == "nickname":
        await state.set_state(ProfileEditStates.nickname)
        await callback.message.answer(
            "Send your new nickname, or skip to clear it.",
            reply_markup=skip_keyboard("nickname"),
        )
    elif field == "preferred_gender":
        await state.set_state(ProfileEditStates.preferred_gender)
        await callback.message.answer(
            "Choose your preferred gender, Any, or Skip to clear the preference.",
            reply_markup=preferred_gender_keyboard(),
        )
    elif field == "interests_json":
        await state.set_state(ProfileEditStates.interests)
        await callback.message.answer(
            "Send your interests separated by commas, or skip to clear them.",
            reply_markup=skip_keyboard("interests"),
        )
    else:
        raise UserVisibleError("That profile field is not available.")

    await callback.answer()


@router.message(ProfileEditStates.age)
async def edit_profile_age(
    message: Message,
    state: FSMContext,
    services: ServiceContainer,
) -> None:
    age = services.user_service.validate_age(message.text or "")
    await services.user_service.update_profile_field(
        message.from_user.id,
        field_name="age",
        value=age,
    )
    await finish_profile_edit(message, state, services)


@router.callback_query(ProfileEditStates.gender, RegistrationCallback.filter(F.action == "gender"))
async def edit_profile_gender(
    callback: CallbackQuery,
    state: FSMContext,
    services: ServiceContainer,
) -> None:
    await services.user_service.update_profile_field(
        callback.from_user.id,
        field_name="gender",
        value=Gender(callback.data.split(":")[-1]),
    )
    await callback.answer("Gender updated.")
    await state.clear()
    user = await services.user_service.require_registered_user(callback.from_user.id)
    await callback.message.answer(
        services.user_service.format_profile(user),
        reply_markup=profile_keyboard(),
    )


@router.message(ProfileEditStates.nickname)
async def edit_profile_nickname(
    message: Message,
    state: FSMContext,
    services: ServiceContainer,
) -> None:
    nickname = services.user_service.validate_nickname(message.text or "")
    await services.user_service.update_profile_field(
        message.from_user.id,
        field_name="nickname",
        value=nickname,
    )
    await finish_profile_edit(message, state, services)


@router.callback_query(
    ProfileEditStates.nickname,
    RegistrationCallback.filter(F.action == "nickname", F.value == "skip"),
)
async def edit_profile_nickname_skip(
    callback: CallbackQuery,
    state: FSMContext,
    services: ServiceContainer,
) -> None:
    await services.user_service.update_profile_field(
        callback.from_user.id,
        field_name="nickname",
        value=None,
    )
    await state.clear()
    user = await services.user_service.require_registered_user(callback.from_user.id)
    await callback.message.answer(
        services.user_service.format_profile(user),
        reply_markup=profile_keyboard(),
    )
    await callback.answer("Nickname cleared.")


@router.callback_query(
    ProfileEditStates.preferred_gender,
    RegistrationCallback.filter(F.action == "preferred_gender"),
)
async def edit_profile_preferred_gender(
    callback: CallbackQuery,
    state: FSMContext,
    services: ServiceContainer,
) -> None:
    value = callback.data.split(":")[-1]
    preferred_gender = None if value == "skip" else PreferredGender(value)
    await services.user_service.update_profile_field(
        callback.from_user.id,
        field_name="preferred_gender",
        value=preferred_gender,
    )
    await state.clear()
    user = await services.user_service.require_registered_user(callback.from_user.id)
    await callback.message.answer(
        services.user_service.format_profile(user),
        reply_markup=profile_keyboard(),
    )
    await callback.answer("Preference updated.")


@router.message(ProfileEditStates.interests)
async def edit_profile_interests(
    message: Message,
    state: FSMContext,
    services: ServiceContainer,
) -> None:
    interests = services.user_service.validate_interests(message.text or "")
    await services.user_service.update_profile_field(
        message.from_user.id,
        field_name="interests_json",
        value=interests,
    )
    await finish_profile_edit(message, state, services)


@router.callback_query(
    ProfileEditStates.interests,
    RegistrationCallback.filter(F.action == "interests", F.value == "skip"),
)
async def edit_profile_interests_skip(
    callback: CallbackQuery,
    state: FSMContext,
    services: ServiceContainer,
) -> None:
    await services.user_service.update_profile_field(
        callback.from_user.id,
        field_name="interests_json",
        value=[],
    )
    await state.clear()
    user = await services.user_service.require_registered_user(callback.from_user.id)
    await callback.message.answer(
        services.user_service.format_profile(user),
        reply_markup=profile_keyboard(),
    )
    await callback.answer("Interests cleared.")


async def finish_profile_edit(
    message: Message,
    state: FSMContext,
    services: ServiceContainer,
) -> None:
    await state.clear()
    user = await services.user_service.require_registered_user(message.from_user.id)
    await message.answer(
        services.user_service.format_profile(user),
        reply_markup=profile_keyboard(),
    )
