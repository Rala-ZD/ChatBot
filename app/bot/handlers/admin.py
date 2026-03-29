from __future__ import annotations

import uuid

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

from app.bot.filters.admin import AdminFilter
from app.services.container import ServiceContainer

router = Router(name="admin")


@router.message(AdminFilter(), Command("ban"))
async def ban_user(
    message: Message,
    services: ServiceContainer,
) -> None:
    parts = (message.text or "").split(maxsplit=2)
    if len(parts) < 3:
        await message.answer("Usage: /ban <internal_user_id> <reason>")
        return
    await services.moderation_service.ban_user(
        user_id=int(parts[1]),
        reason=parts[2],
        banned_by=message.from_user.id,
    )
    await message.answer("User banned.")


@router.message(AdminFilter(), Command("unban"))
async def unban_user(
    message: Message,
    services: ServiceContainer,
) -> None:
    parts = (message.text or "").split(maxsplit=1)
    if len(parts) < 2:
        await message.answer("Usage: /unban <internal_user_id>")
        return
    await services.moderation_service.unban_user(
        user_id=int(parts[1]),
        revoked_by=message.from_user.id,
    )
    await message.answer("User unbanned.")


@router.message(AdminFilter(), Command("reports"))
async def list_reports(
    message: Message,
    services: ServiceContainer,
) -> None:
    reports = await services.admin_service.list_reports(limit=10)
    if not reports:
        await message.answer("No reports found.")
        return
    lines = ["<b>Recent reports</b>"]
    for report in reports:
        lines.append(
            f"#{report.id} session={report.session_id} reporter={report.reporter_user_id} "
            f"reported={report.reported_user_id} reason={report.reason}"
        )
    await message.answer("\n".join(lines))


@router.message(AdminFilter(), Command("session"))
async def session_detail(
    message: Message,
    services: ServiceContainer,
) -> None:
    parts = (message.text or "").split(maxsplit=1)
    if len(parts) < 2:
        await message.answer("Usage: /session <session_uuid>")
        return
    session_id = uuid.UUID(parts[1])
    detail = await services.admin_service.get_session_detail(session_id)
    await message.answer(
        "<b>Session</b>\n"
        f"ID: <code>{detail.session_id}</code>\n"
        f"Status: {detail.status}\n"
        f"Started: {detail.started_at.isoformat()}\n"
        f"Ended: {detail.ended_at.isoformat() if detail.ended_at else '-'}\n"
        f"End reason: {detail.end_reason or '-'}\n"
        f"Messages: {len(detail.messages)}"
    )
