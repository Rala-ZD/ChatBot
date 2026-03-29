from __future__ import annotations

from aiogram.filters import BaseFilter
from aiogram.types import Message

from app.services.container import ServiceContainer


class AdminFilter(BaseFilter):
    async def __call__(self, message: Message, services: ServiceContainer) -> bool:
        return message.from_user is not None and services.settings.is_admin(message.from_user.id)
