from __future__ import annotations

import re
from datetime import timedelta
from typing import TYPE_CHECKING, Literal

from aiogram.types import Message

from app.utils.enums import MessageType
from app.utils.time import utcnow

if TYPE_CHECKING:
    from app.db.models.session import ChatSession
    from app.db.models.user import User


EARLY_CHAT_RESTRICTION_SECONDS = 90
LINK_PATTERN = re.compile(
    r"(?i)(https?://\S+|www\.\S+|\b(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,24}(?:/\S*)?\b)"
)
TELEGRAM_HANDLE_PATTERN = re.compile(r"(?<![\w@.])@[A-Za-z][A-Za-z0-9_]{4,31}\b")
RestrictedContentReason = Literal["link", "handle", "media"]


def resolve_message_type(message: Message) -> MessageType:
    if message.text:
        return MessageType.TEXT
    if message.photo:
        return MessageType.PHOTO
    if message.video:
        return MessageType.VIDEO
    if message.voice:
        return MessageType.VOICE
    if message.document:
        return MessageType.DOCUMENT
    if message.sticker:
        return MessageType.STICKER
    return MessageType.UNSUPPORTED


def extract_file_metadata(message: Message) -> tuple[str | None, str | None]:
    if message.photo:
        return message.photo[-1].file_id, message.photo[-1].file_unique_id
    if message.video:
        return message.video.file_id, message.video.file_unique_id
    if message.voice:
        return message.voice.file_id, message.voice.file_unique_id
    if message.document:
        return message.document.file_id, message.document.file_unique_id
    if message.sticker:
        return message.sticker.file_id, message.sticker.file_unique_id
    return None, None


def supported_for_relay(message: Message) -> bool:
    return resolve_message_type(message) != MessageType.UNSUPPORTED


def is_early_chat_restricted(chat_session: "ChatSession", user: "User") -> bool:
    if user.has_active_vip():
        return False
    if chat_session.started_at is None:
        return False
    return utcnow() < chat_session.started_at + timedelta(seconds=EARLY_CHAT_RESTRICTION_SECONDS)


def message_has_restricted_content(message: Message) -> RestrictedContentReason | None:
    if message.text:
        if LINK_PATTERN.search(message.text):
            return "link"
        if TELEGRAM_HANDLE_PATTERN.search(message.text):
            return "handle"
        return None
    return "media"
