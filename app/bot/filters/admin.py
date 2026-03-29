from __future__ import annotations

from aiogram.filters import Filter
from aiogram.types import CallbackQuery, Message

from app.config import Settings


class AdminFilter(Filter):
    async def __call__(
        self,
        event: Message | CallbackQuery,
        settings: Settings,
    ) -> bool:
        user = event.from_user
        return bool(user and user.id in settings.admin_user_ids)

