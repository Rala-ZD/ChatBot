from __future__ import annotations

from app.db.repositories.ban_repository import BanRepository
from app.db.repositories.session_repository import SessionRepository
from app.db.repositories.user_repository import UserRepository
from app.db.repositories.waiting_queue_repository import WaitingQueueRepository
from app.services.exceptions import NotFoundError


class AdminService:
    def __init__(
        self,
        user_repository: UserRepository,
        ban_repository: BanRepository,
        session_repository: SessionRepository,
        waiting_queue_repository: WaitingQueueRepository,
    ) -> None:
        self.user_repository = user_repository
        self.ban_repository = ban_repository
        self.session_repository = session_repository
        self.waiting_queue_repository = waiting_queue_repository

    async def lookup_user(self, user_id: int) -> str:
        user = await self.user_repository.get_by_id(user_id)
        if user is None:
            raise NotFoundError("User not found.")

        active_ban = await self.ban_repository.get_active_by_user_id(user_id)
        active_session = await self.session_repository.get_active_by_user_id(user_id)
        queue_entry = await self.waiting_queue_repository.get_active_by_user_id(user_id)

        return (
            f"User #{user.id}\n"
            f"telegram_id={user.telegram_id}\n"
            f"registered={user.is_registered}\n"
            f"banned={user.is_banned}\n"
            f"active_ban_id={active_ban.id if active_ban else '-'}\n"
            f"queue_status={'waiting' if queue_entry else 'idle'}\n"
            f"active_session_id={active_session.id if active_session else '-'}\n"
            f"nickname={user.nickname or '-'}\n"
            f"gender={user.gender.value if user.gender else '-'}\n"
            f"preferred_gender={user.preferred_gender.value if user.preferred_gender else '-'}"
        )

