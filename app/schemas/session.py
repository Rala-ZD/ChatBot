from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel

from app.utils.enums import EndReason, MessageType, SessionStatus


class SessionMessageCreate(BaseModel):
    session_id: int
    sender_user_id: int
    sender_chat_id: int
    source_message_id: int
    message_type: MessageType
    telegram_message_id: int
    relay_chat_id: int | None = None
    relay_message_id: int | None = None
    text_content: str | None = None
    caption: str | None = None
    file_id: str | None = None
    file_unique_id: str | None = None
    metadata_json: dict[str, str] | None = None


class SessionEndResult(BaseModel):
    session_id: int
    status: SessionStatus
    end_reason: EndReason
    ended_at: datetime
    already_ended: bool = False

