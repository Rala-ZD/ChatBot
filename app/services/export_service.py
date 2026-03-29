from __future__ import annotations

from aiogram import Bot
from aiogram.exceptions import TelegramAPIError

from app.config import Settings
from app.db.models.session import ChatSession
from app.db.models.session_message import SessionMessage
from app.db.models.user import User
from app.db.repositories.session_message_repository import SessionMessageRepository
from app.db.repositories.session_repository import SessionRepository
from app.logging import get_logger
from app.utils.enums import MessageType
from app.utils.text import chunk_text, format_interests
from app.utils.time import humanize_duration, utcnow


class ExportService:
    def __init__(
        self,
        settings: Settings,
        bot: Bot,
        session_repository: SessionRepository,
        session_message_repository: SessionMessageRepository,
    ) -> None:
        self.settings = settings
        self.bot = bot
        self.session_repository = session_repository
        self.session_message_repository = session_message_repository
        self.logger = get_logger(__name__)

    async def export_session(self, session_id: int) -> None:
        chat_session = await self.session_repository.get_with_details(session_id)
        if chat_session is None or chat_session.exported_at is not None:
            return

        messages = await self.session_message_repository.list_for_session(session_id)
        transcript = self._render_transcript(chat_session, messages)
        chunks = chunk_text(transcript)

        first_message_id: int | None = None
        for chunk in chunks:
            sent = await self.bot.send_message(self.settings.admin_channel_id, chunk)
            if first_message_id is None:
                first_message_id = sent.message_id

        if first_message_id is not None:
            await self._export_media(chat_session, messages, first_message_id)

        chat_session.exported_at = utcnow()
        await self.session_repository.save(chat_session)
        await self.session_repository.session.commit()

    def _render_transcript(
        self,
        chat_session: ChatSession,
        messages: list[SessionMessage],
    ) -> str:
        user1 = chat_session.user1
        user2 = chat_session.user2

        header_lines = [
            f"Session #{chat_session.id}",
            f"Started: {chat_session.started_at.isoformat()}",
            f"Ended: {chat_session.ended_at.isoformat() if chat_session.ended_at else 'active'}",
            f"Duration: {humanize_duration(chat_session.started_at, chat_session.ended_at)}",
            f"End reason: {chat_session.end_reason.value if chat_session.end_reason else 'unknown'}",
            "",
            "User 1:",
            self._format_user_metadata(user1),
            "",
            "User 2:",
            self._format_user_metadata(user2),
            "",
            "Transcript:",
        ]

        transcript_lines = [self._render_message_line(chat_session, message) for message in messages]
        return "\n".join(header_lines + transcript_lines)

    def _format_user_metadata(self, user: User) -> str:
        interests = format_interests(user.interests_json)
        return (
            f"- internal_id={user.id}, telegram_id={user.telegram_id}, username={user.username or '-'}, "
            f"first_name={user.first_name or '-'}, nickname={user.nickname or '-'}, age={user.age or '-'}, "
            f"gender={user.gender.value if user.gender else '-'}, preferred={user.preferred_gender.value}, "
            f"interests={interests}, banned={user.is_banned}"
        )

    def _render_message_line(self, chat_session: ChatSession, message: SessionMessage) -> str:
        actor = "User 1" if message.sender_user_id == chat_session.user1_id else "User 2"
        timestamp = message.created_at.isoformat()
        if message.message_type == MessageType.TEXT:
            body = message.text_content or ""
        else:
            extra = f" | caption={message.caption}" if message.caption else ""
            body = f"[{message.message_type.value}]{extra}"
        return f"[{timestamp}] {actor}: {body}"

    async def _export_media(
        self,
        chat_session: ChatSession,
        messages: list[SessionMessage],
        first_message_id: int,
    ) -> None:
        for message in messages:
            if message.message_type in {MessageType.TEXT, MessageType.UNSUPPORTED}:
                continue

            actor = "User 1" if message.sender_user_id == chat_session.user1_id else "User 2"
            note = await self.bot.send_message(
                self.settings.admin_channel_id,
                (
                    f"Media from {actor} in session #{chat_session.id}\n"
                    f"type={message.message_type.value}, source_message_id={message.source_message_id}"
                ),
                reply_to_message_id=first_message_id,
            )
            try:
                await self.bot.copy_message(
                    chat_id=self.settings.admin_channel_id,
                    from_chat_id=message.sender_chat_id,
                    message_id=message.source_message_id,
                    reply_to_message_id=note.message_id,
                )
            except TelegramAPIError as exc:
                self.logger.warning(
                    "media_export_failed",
                    session_id=chat_session.id,
                    message_id=message.id,
                    error=str(exc),
                )
                await self.bot.send_message(
                    self.settings.admin_channel_id,
                    (
                        f"Fallback: could not copy media for session #{chat_session.id}. "
                        f"file_id={message.file_id or '-'}"
                    ),
                    reply_to_message_id=note.message_id,
                )

