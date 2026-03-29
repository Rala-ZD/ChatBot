from __future__ import annotations

from aiogram.filters import Filter
from aiogram.types import Message

from app.db.models.user import User
from app.services.session_service import SessionService


class ActiveSessionFilter(Filter):
    def __init__(self, required: bool = True) -> None:
        self.required = required

    async def __call__(
        self,
        message: Message,
        app_user: User | None,
        session_service: SessionService,
    ) -> bool:
        if app_user is None:
            return not self.required
        active = await session_service.get_active_session_for_user(app_user.id)
        return bool(active) if self.required else not active
