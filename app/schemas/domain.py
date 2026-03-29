from __future__ import annotations

import uuid
from dataclasses import dataclass

from app.db.models import Session, SessionMessage, User


@dataclass(slots=True)
class MatchResult:
    matched: bool
    waiting: bool
    session_id: uuid.UUID | None = None
    partner_user_id: int | None = None


@dataclass(slots=True)
class ActiveSessionContext:
    session: Session
    user: User
    partner: User


@dataclass(slots=True)
class RelayPayload:
    message_type: str
    text_content: str | None
    caption: str | None
    file_id: str | None
    file_unique_id: str | None


@dataclass(slots=True)
class SessionEndResult:
    ended: bool
    session_id: uuid.UUID | None
    partner_user_id: int | None = None


@dataclass(slots=True)
class TranscriptBundle:
    session: Session
    user1: User
    user2: User
    messages: list[SessionMessage]
