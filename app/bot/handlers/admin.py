from __future__ import annotations

from aiogram import F, Router
from aiogram.enums import ChatType
from aiogram.filters import Command
from aiogram.types import Message

from app.bot.filters.admin import AdminFilter
from app.db.models.user import User
from app.schemas.moderation import BanCreate
from app.services.admin_service import AdminService
from app.services.moderation_service import ModerationService
from app.services.session_service import SessionService
from app.utils.enums import EndReason

router = Router(name="admin")
router.message.filter(F.chat.type == ChatType.PRIVATE, AdminFilter())


@router.message(Command("lookup"))
async def lookup_user(message: Message, admin_service: AdminService) -> None:
    parts = (message.text or "").split(maxsplit=1)
    if len(parts) != 2:
        await message.answer("Usage: /lookup <internal_user_id>")
        return
    await message.answer(await admin_service.lookup_user(int(parts[1])))


@router.message(Command("ban"))
async def ban_user(
    message: Message,
    app_user: User,
    moderation_service: ModerationService,
    session_service: SessionService,
) -> None:
    parts = (message.text or "").split(maxsplit=2)
    if len(parts) < 3:
        await message.answer("Usage: /ban <internal_user_id> <reason>")
        return

    payload = BanCreate(user_id=int(parts[1]), banned_by=app_user.id, reason=parts[2])
    ban = await moderation_service.ban_user(payload)
    await session_service.end_active_session_for_user(
        payload.user_id,
        EndReason.MODERATION,
        ended_by_user_id=app_user.id,
    )
    await message.answer(f"User #{ban.user_id} is banned.")


@router.message(Command("unban"))
async def unban_user(
    message: Message,
    app_user: User,
    moderation_service: ModerationService,
) -> None:
    parts = (message.text or "").split(maxsplit=1)
    if len(parts) != 2:
        await message.answer("Usage: /unban <internal_user_id>")
        return

    ban = await moderation_service.unban_user(int(parts[1]), app_user.id)
    await message.answer(f"User #{ban.user_id} is unbanned.")
