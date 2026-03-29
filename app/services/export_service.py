from __future__ import annotations

import html
import uuid
from datetime import UTC, datetime

from aiogram import Bot
from aiogram.exceptions import TelegramAPIError
from aiogram.types import BufferedInputFile
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.config import Settings
from app.db.repositories.session_message_repository import SessionMessageRepository
from app.db.repositories.session_repository import SessionRepository
from app.db.repositories.user_repository import UserRepository
from app.db.session import session_scope
from app.schemas.domain import TranscriptBundle
from app.utils.redis import redis_lock
from app.utils.redis_keys import session_export_lock_key


class ExportService:
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

    async def export_session(self, session_id: uuid.UUID) -> bool:
        async with redis_lock(
            self.redis,
            session_export_lock_key(str(session_id)),
            timeout=self.settings.export_lock_seconds,
            blocking_timeout=self.settings.export_lock_seconds,
        ):
            bundle = await self._load_bundle(session_id)
            if bundle is None or bundle.session.exported_at is not None:
                return False

            await self.bot.send_message(
                chat_id=self.settings.admin_channel_id,
                text=self._build_summary(bundle),
            )
            transcript_bytes = self._build_transcript(bundle).encode("utf-8")
            transcript_file = BufferedInputFile(
                transcript_bytes,
                filename=f"session-{bundle.session.id}.txt",
            )
            await self.bot.send_document(
                chat_id=self.settings.admin_channel_id,
                document=transcript_file,
                caption=f"Session {bundle.session.id} transcript",
            )
            await self._copy_media_records(bundle)

            async with session_scope(self.session_factory) as session:
                session_repo = SessionRepository(session)
                await session_repo.mark_exported(session_id, datetime.now(UTC))
            return True

    async def load_bundle(self, session_id: uuid.UUID) -> TranscriptBundle | None:
        return await self._load_bundle(session_id)

    async def _load_bundle(self, session_id: uuid.UUID) -> TranscriptBundle | None:
        async with session_scope(self.session_factory) as session:
            session_repo = SessionRepository(session)
            message_repo = SessionMessageRepository(session)
            user_repo = UserRepository(session)

            chat_session = await session_repo.get_by_id(session_id)
            if chat_session is None:
                return None
            user1 = await user_repo.get_by_id(chat_session.user1_id)
            user2 = await user_repo.get_by_id(chat_session.user2_id)
            if user1 is None or user2 is None:
                return None
            messages = await message_repo.list_for_session(session_id)
            return TranscriptBundle(
                session=chat_session,
                user1=user1,
                user2=user2,
                messages=messages,
            )

    def _build_summary(self, bundle: TranscriptBundle) -> str:
        duration = "unknown"
        if bundle.session.ended_at is not None:
            delta = bundle.session.ended_at - bundle.session.started_at
            duration = str(delta).split(".")[0]
        return (
            "<b>Session export</b>\n"
            f"Session ID: <code>{bundle.session.id}</code>\n"
            f"Started: {bundle.session.started_at.isoformat()}\n"
            f"Ended: {bundle.session.ended_at.isoformat() if bundle.session.ended_at else 'active'}\n"
            f"Duration: {duration}\n"
            f"Status: {bundle.session.status}\n"
            f"End reason: {bundle.session.end_reason or 'unknown'}\n\n"
            f"{self._format_user('User 1', bundle.user1)}\n\n"
            f"{self._format_user('User 2', bundle.user2)}\n\n"
            f"Messages logged: {len(bundle.messages)}"
        )

    def _build_transcript(self, bundle: TranscriptBundle) -> str:
        lines = [
            f"Session ID: {bundle.session.id}",
            f"Started: {bundle.session.started_at.isoformat()}",
            f"Ended: {bundle.session.ended_at.isoformat() if bundle.session.ended_at else 'active'}",
            f"End reason: {bundle.session.end_reason or 'unknown'}",
            "",
            self._format_user_text("User 1", bundle.user1),
            self._format_user_text("User 2", bundle.user2),
            "",
            "Messages:",
        ]
        user_lookup = {bundle.user1.id: bundle.user1, bundle.user2.id: bundle.user2}
        for message in bundle.messages:
            sender = user_lookup.get(message.sender_user_id)
            sender_label = sender.nickname or sender.first_name or f"User {message.sender_user_id}"
            content = message.text_content or message.caption or "[media]"
            lines.append(
                f"[{message.created_at.isoformat()}] {sender_label} ({message.message_type}): {content}"
            )
        return "\n".join(lines)

    def _format_user(self, label: str, user: object) -> str:
        payload = user.profile_snapshot()  # type: ignore[attr-defined]
        return (
            f"<b>{label}</b>\n"
            f"Internal ID: {payload['id']}\n"
            f"Telegram ID: {payload['telegram_id']}\n"
            f"Username: {html.escape(payload['username'] or '-')}\n"
            f"First name: {html.escape(payload['first_name'] or '-')}\n"
            f"Nickname: {html.escape(payload['nickname'] or '-')}\n"
            f"Age: {payload['age'] or '-'}\n"
            f"Gender: {payload['gender'] or '-'}\n"
            f"Preferred gender: {payload['preferred_gender'] or '-'}\n"
            f"Interests: {', '.join(payload['interests']) if payload['interests'] else '-'}\n"
            f"Registered: {payload['is_registered']}\n"
            f"Banned: {payload['is_banned']}"
        )

    def _format_user_text(self, label: str, user: object) -> str:
        payload = user.profile_snapshot()  # type: ignore[attr-defined]
        return (
            f"{label}: internal_id={payload['id']}, telegram_id={payload['telegram_id']}, "
            f"username={payload['username']}, nickname={payload['nickname']}, age={payload['age']}, "
            f"gender={payload['gender']}, preferred_gender={payload['preferred_gender']}, "
            f"interests={payload['interests']}"
        )

    async def _copy_media_records(self, bundle: TranscriptBundle) -> None:
        user_lookup = {bundle.user1.id: bundle.user1, bundle.user2.id: bundle.user2}
        for index, message in enumerate(bundle.messages, start=1):
            if not message.file_id:
                continue
            sender = user_lookup.get(message.sender_user_id)
            sender_internal_id = sender.id if sender is not None else message.sender_user_id
            source_chat_id = self._resolve_export_source_chat_id(bundle, message.sender_user_id)
            note = (
                f"Session {bundle.session.id} media #{index}\n"
                f"From internal user {sender_internal_id}\n"
                f"Type: {message.message_type}"
            )
            await self.bot.send_message(chat_id=self.settings.admin_channel_id, text=note)
            if source_chat_id is None:
                await self.bot.send_message(
                    chat_id=self.settings.admin_channel_id,
                    text=(
                        "Could not determine relayed media source.\n"
                        f"Session ID: {bundle.session.id}\n"
                        f"Record ID: {message.id}\n"
                        f"Type: {message.message_type}\n"
                        f"Sender internal ID: {sender_internal_id}\n"
                        f"Stored file_id: {message.file_id or '-'}"
                    ),
                )
                continue
            try:
                await self.bot.copy_message(
                    chat_id=self.settings.admin_channel_id,
                    from_chat_id=source_chat_id,
                    message_id=message.telegram_message_id,
                )
            except TelegramAPIError:
                await self.bot.send_message(
                    chat_id=self.settings.admin_channel_id,
                    text=(
                        "Could not copy relayed media to the admin channel.\n"
                        f"Session ID: {bundle.session.id}\n"
                        f"Record ID: {message.id}\n"
                        f"Relayed message ID: {message.telegram_message_id}\n"
                        f"Type: {message.message_type}\n"
                        f"Sender internal ID: {sender_internal_id}\n"
                        f"Stored file_id: {message.file_id or '-'}"
                    ),
                )

    def _resolve_export_source_chat_id(
        self,
        bundle: TranscriptBundle,
        sender_user_id: int,
    ) -> int | None:
        if sender_user_id == bundle.user1.id:
            return bundle.user2.telegram_id
        if sender_user_id == bundle.user2.id:
            return bundle.user1.telegram_id
        return None
