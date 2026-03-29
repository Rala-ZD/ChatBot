from __future__ import annotations

import random
from datetime import UTC, datetime, timedelta

from aiogram import Bot
from aiogram.exceptions import TelegramAPIError
from aiogram.types import User as TelegramUser
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.config import Settings
from app.bot.keyboards.menus import chat_menu_keyboard
from app.db.models import PreferredGender, QueueStatus, SessionEndReason, User
from app.db.repositories.ban_repository import BanRepository
from app.db.repositories.session_repository import SessionRepository
from app.db.repositories.user_repository import UserRepository
from app.db.repositories.waiting_queue_repository import WaitingQueueRepository
from app.db.session import session_scope
from app.schemas.domain import MatchResult
from app.utils.exceptions import ConflictError, UserVisibleError
from app.utils.redis import redis_lock
from app.utils.redis_keys import matchmaking_lock_key, waiting_queue_members_key


class MatchService:
    def __init__(
        self,
        session_factory: async_sessionmaker,
        redis: Redis,
        bot: Bot,
        settings: Settings,
    ) -> None:
        self.session_factory = session_factory
        self.redis = redis
        self.bot = bot
        self.settings = settings

    async def enqueue_user(self, telegram_user: TelegramUser) -> MatchResult:
        async with redis_lock(
            self.redis,
            matchmaking_lock_key(),
            timeout=self.settings.match_lock_seconds,
            blocking_timeout=self.settings.match_lock_seconds,
        ):
            async with session_scope(self.session_factory) as session:
                user_repo = UserRepository(session)
                ban_repo = BanRepository(session)
                queue_repo = WaitingQueueRepository(session)
                session_repo = SessionRepository(session)

                user = await user_repo.get_or_create_by_telegram_identity(
                    telegram_id=telegram_user.id,
                    username=telegram_user.username,
                    first_name=telegram_user.first_name,
                )
                await self._assert_can_join(user, queue_repo, session_repo, ban_repo)

                waiting_entry = await queue_repo.get_active_entry_for_user(user.id)
                if waiting_entry is None:
                    waiting_entry = await queue_repo.add_waiting_user(user.id)
                    await self.redis.sadd(waiting_queue_members_key(), user.id)

                candidates = await queue_repo.get_candidates(user.id)
                match_user = self._pick_candidate(
                    current_user=user,
                    current_joined_at=waiting_entry.joined_at,
                    candidates=candidates,
                )
                if match_user is None:
                    return MatchResult(matched=False, waiting=True)

                matched_session = await session_repo.create_session(user.id, match_user.id)
                user.is_in_chat = True
                match_user.is_in_chat = True
                await queue_repo.mark_users_as([user.id, match_user.id], QueueStatus.MATCHED)
                await self.redis.srem(waiting_queue_members_key(), user.id, match_user.id)
                result = MatchResult(
                    matched=True,
                    waiting=False,
                    session_id=matched_session.id,
                    partner_user_id=match_user.id,
                )

            await self._notify_match(matched_session.id, user, match_user)
            return result

    async def cancel_waiting(self, telegram_id: int) -> bool:
        async with redis_lock(
            self.redis,
            matchmaking_lock_key(),
            timeout=self.settings.match_lock_seconds,
            blocking_timeout=self.settings.match_lock_seconds,
        ):
            async with session_scope(self.session_factory) as session:
                user_repo = UserRepository(session)
                queue_repo = WaitingQueueRepository(session)
                user = await user_repo.get_by_telegram_id(telegram_id)
                if user is None:
                    return False
                entry = await queue_repo.get_active_entry_for_user(user.id)
                if entry is None:
                    return False
                await queue_repo.cancel_all_waiting_for_user(user.id)
                await self.redis.srem(waiting_queue_members_key(), user.id)
                return True

    async def cancel_waiting_by_user_id(self, user_id: int) -> None:
        async with redis_lock(
            self.redis,
            matchmaking_lock_key(),
            timeout=self.settings.match_lock_seconds,
            blocking_timeout=self.settings.match_lock_seconds,
        ):
            async with session_scope(self.session_factory) as session:
                queue_repo = WaitingQueueRepository(session)
                await queue_repo.cancel_all_waiting_for_user(user_id)
                await self.redis.srem(waiting_queue_members_key(), user_id)

    async def is_waiting(self, telegram_id: int) -> bool:
        async with session_scope(self.session_factory) as session:
            user_repo = UserRepository(session)
            queue_repo = WaitingQueueRepository(session)
            user = await user_repo.get_by_telegram_id(telegram_id)
            if user is None:
                return False
            return await queue_repo.get_active_entry_for_user(user.id) is not None

    async def _assert_can_join(
        self,
        user: User,
        queue_repo: WaitingQueueRepository,
        session_repo: SessionRepository,
        ban_repo: BanRepository,
    ) -> None:
        if not user.is_registered:
            raise UserVisibleError("Please complete registration before starting a chat.")
        if user.is_banned or await ban_repo.get_active_by_user_id(user.id):
            raise UserVisibleError("Your access is currently restricted.")
        if user.is_in_chat or await session_repo.get_active_by_user_id(user.id):
            raise ConflictError("You are already in an active chat.")
        if await queue_repo.get_active_entry_for_user(user.id):
            raise ConflictError("You are already searching for a stranger.")

    def _pick_candidate(
        self,
        *,
        current_user: User,
        current_joined_at: datetime,
        candidates: list[tuple[object, User]],
    ) -> User | None:
        strict_matches: list[User] = []
        relaxed_matches: list[User] = []
        now = datetime.now(UTC)
        relax_after = timedelta(seconds=self.settings.match_soft_preference_after_seconds)

        for queue_entry, candidate in candidates:
            if candidate.id == current_user.id:
                continue
            if self._mutually_compatible(current_user, candidate):
                strict_matches.append(candidate)
                continue
            current_waited_long_enough = now - current_joined_at >= relax_after
            candidate_waited_long_enough = now - queue_entry.joined_at >= relax_after
            if current_waited_long_enough or candidate_waited_long_enough:
                relaxed_matches.append(candidate)

        pool = strict_matches or relaxed_matches
        if not pool:
            return None
        return random.choice(pool)

    def _mutually_compatible(self, user: User, candidate: User) -> bool:
        return self._matches_preference(user, candidate) and self._matches_preference(candidate, user)

    def _matches_preference(self, user: User, candidate: User) -> bool:
        if user.preferred_gender in (None, PreferredGender.ANY):
            return True
        if candidate.gender is None:
            return False
        return user.preferred_gender.value == candidate.gender.value

    async def _notify_match(self, session_id, user: User, partner: User) -> None:
        text = (
            "<b>You are connected.</b>\n"
            "Say hi and keep the conversation respectful."
        )
        try:
            await self.bot.send_message(
                chat_id=user.telegram_id,
                text=text,
                reply_markup=chat_menu_keyboard(),
            )
            await self.bot.send_message(
                chat_id=partner.telegram_id,
                text=text,
                reply_markup=chat_menu_keyboard(),
            )
        except TelegramAPIError as exc:
            async with session_scope(self.session_factory) as session:
                session_repo = SessionRepository(session)
                user_repo = UserRepository(session)
                active_session = await session_repo.get_by_id(session_id)
                if active_session is not None:
                    await session_repo.end_session(
                        session_id,
                        ended_at=datetime.now(UTC),
                        end_reason=SessionEndReason.INTERNAL_FAILURE.value,
                    )
                user_record = await user_repo.get_by_id(user.id)
                partner_record = await user_repo.get_by_id(partner.id)
                if user_record is not None:
                    user_record.is_in_chat = False
                if partner_record is not None:
                    partner_record.is_in_chat = False
            raise UserVisibleError("A match was found, but one side could not be reached. Please try again.") from exc
