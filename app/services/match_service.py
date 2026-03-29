from __future__ import annotations

import asyncio

from aiogram import Bot
from aiogram.exceptions import TelegramAPIError

from app.bot.keyboards.chat import active_chat_keyboard
from app.db.models.user import User
from app.db.repositories.session_repository import SessionRepository
from app.db.repositories.user_repository import UserRepository
from app.db.repositories.waiting_queue_repository import WaitingQueueRepository
from app.logging import get_logger
from app.schemas.common import MatchOutcome
from app.services.exceptions import AccessDeniedError, ConflictError
from app.services.ops_service import OpsService
from app.services.queue_service import QueueService
from app.services.session_service import SessionService
from app.utils.enums import PreferredGender, QueueStatus
from app.utils.text import MATCH_FOUND_TEXT
from app.utils.time import utcnow

CANCEL_LOCK_RETRIES = 5
CANCEL_LOCK_RETRY_DELAY_SECONDS = 0.05


class MatchService:
    def __init__(
        self,
        bot: Bot,
        user_repository: UserRepository,
        waiting_queue_repository: WaitingQueueRepository,
        session_repository: SessionRepository,
        session_service: SessionService,
        queue_service: QueueService,
        ops_service: OpsService,
        match_scan_limit: int,
    ) -> None:
        self.bot = bot
        self.user_repository = user_repository
        self.waiting_queue_repository = waiting_queue_repository
        self.session_repository = session_repository
        self.session_service = session_service
        self.queue_service = queue_service
        self.ops_service = ops_service
        self.match_scan_limit = match_scan_limit
        self.logger = get_logger(__name__)

    async def start(self, user: User) -> MatchOutcome:
        if user.is_banned:
            raise AccessDeniedError("Your access to this bot is currently restricted.")
        if not user.is_registered:
            raise ConflictError("Please finish registration before joining chat.")

        async with self.queue_service.user_lock(user.id) as user_locked:
            if not user_locked:
                raise ConflictError("Please try again in a moment.")

            active_session = await self.session_repository.get_active_by_user_id_for_update(user.id)
            if active_session is not None:
                raise ConflictError("You are already in an active chat.")

            existing_queue = await self.waiting_queue_repository.get_active_by_user_id_for_update(user.id)
            if existing_queue is not None or await self.queue_service.is_queued(user.id):
                return MatchOutcome(status="queued")

            await self.waiting_queue_repository.add_waiting(user.id)
            await self.queue_service.enqueue_user(user)
            await self.waiting_queue_repository.session.commit()
            await self.ops_service.record_search_start()
            self.logger.info("match_enqueued", user_id=user.id)

        async with self.queue_service.matchmaking_lock() as locked:
            if not locked:
                return MatchOutcome(status="queued")

            candidate = await self._find_candidate_for(user)
            if candidate is None:
                await self.waiting_queue_repository.increment_attempts(user.id)
                await self.waiting_queue_repository.session.commit()
                return MatchOutcome(status="queued")

            session = await self._finalize_match(user.id, candidate.id)
            if session is None:
                await self.waiting_queue_repository.increment_attempts(user.id)
                await self.waiting_queue_repository.session.commit()
                return MatchOutcome(status="queued")

            await self._notify_match(user, candidate)
            return MatchOutcome(
                status="matched",
                session_id=session.id,
                partner_user_id=candidate.id,
            )

    async def cancel_waiting(self, user_id: int) -> bool:
        for attempt in range(CANCEL_LOCK_RETRIES):
            async with self.queue_service.user_lock(user_id) as locked:
                if not locked:
                    if attempt < CANCEL_LOCK_RETRIES - 1:
                        await asyncio.sleep(CANCEL_LOCK_RETRY_DELAY_SECONDS)
                        continue
                    return False

                active = await self.waiting_queue_repository.get_active_by_user_id_for_update(user_id)
                if active is None and not await self.queue_service.is_queued(user_id):
                    return False

                if active is not None:
                    await self.waiting_queue_repository.update_status(user_id, QueueStatus.CANCELLED)
                await self.queue_service.remove_user(user_id)
                await self.waiting_queue_repository.session.commit()
                await self.ops_service.record_cancel()
                self.logger.info("match_cancelled", user_id=user_id)
                return True

        return False

    async def is_waiting(self, user_id: int) -> bool:
        active = await self.waiting_queue_repository.get_active_by_user_id(user_id)
        if active is None:
            return False
        return await self.queue_service.is_queued(user_id)

    async def _find_candidate_for(self, user: User) -> User | None:
        for candidate_id in await self.queue_service.get_waiting_user_ids(self.match_scan_limit):
            if candidate_id == user.id:
                continue
            candidate = await self.user_repository.get_by_id(candidate_id)
            if candidate is None or candidate.is_banned:
                continue
            if await self.session_repository.get_active_by_user_id(candidate.id):
                continue
            if not self._preferences_compatible(user, candidate):
                continue
            return candidate
        return None

    def _preferences_compatible(self, left: User, right: User) -> bool:
        if left.gender is None or right.gender is None:
            return False

        left_pref = left.preferred_gender if left.has_active_vip() else PreferredGender.ANY
        right_pref = right.preferred_gender if right.has_active_vip() else PreferredGender.ANY
        left_accepts = left_pref == PreferredGender.ANY or left_pref.value == right.gender.value
        right_accepts = right_pref == PreferredGender.ANY or right_pref.value == left.gender.value
        return left_accepts and right_accepts

    async def _finalize_match(self, user_id: int, candidate_id: int):
        async with self.queue_service.multi_user_lock([user_id, candidate_id]) as locked:
            if not locked:
                return None

            if not await self._user_is_waiting_for_update(user_id):
                return None
            if not await self._user_is_waiting_for_update(candidate_id):
                return None
            if await self.session_repository.get_active_by_user_id_for_update(user_id):
                return None
            if await self.session_repository.get_active_by_user_id_for_update(candidate_id):
                return None

            user_joined = await self.queue_service.get_joined_timestamp(user_id)
            candidate_joined = await self.queue_service.get_joined_timestamp(candidate_id)

            session = await self.session_service.create_session(user_id, candidate_id)
            await self.waiting_queue_repository.update_status(user_id, QueueStatus.MATCHED)
            await self.waiting_queue_repository.update_status(candidate_id, QueueStatus.MATCHED)
            await self.queue_service.remove_user(user_id)
            await self.queue_service.remove_user(candidate_id)
            await self.waiting_queue_repository.session.commit()

            average_wait_seconds = self._average_wait_seconds(user_joined, candidate_joined)
            await self.ops_service.record_match_created(average_wait_seconds)
            self.logger.info(
                "match_created",
                session_id=session.id,
                user1_id=min(user_id, candidate_id),
                user2_id=max(user_id, candidate_id),
                average_wait_seconds=average_wait_seconds,
            )
            return session

    async def _user_is_waiting_for_update(self, user_id: int) -> bool:
        active = await self.waiting_queue_repository.get_active_by_user_id_for_update(user_id)
        if active is None:
            return False
        return await self.queue_service.is_queued(user_id)

    def _average_wait_seconds(
        self,
        first_joined: float | None,
        second_joined: float | None,
    ) -> int:
        now = utcnow().timestamp()
        joined_values = [value for value in (first_joined, second_joined) if value is not None]
        if not joined_values:
            return 0
        total_wait = sum(max(int(now - value), 0) for value in joined_values)
        return int(total_wait / len(joined_values))

    async def _notify_match(self, left: User, right: User) -> None:
        copy = MATCH_FOUND_TEXT
        for telegram_id in (left.telegram_id, right.telegram_id):
            try:
                await self.bot.send_message(
                    telegram_id,
                    copy,
                    reply_markup=active_chat_keyboard(),
                )
            except TelegramAPIError as exc:
                self.logger.warning("match_notify_failed", telegram_id=telegram_id, error=str(exc))
