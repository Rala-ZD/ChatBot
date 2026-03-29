from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class HealthResponse(BaseModel):
    status: str
    service: str


class BanRequest(BaseModel):
    reason: str


class UserSummaryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    telegram_id: int
    username: str | None
    first_name: str | None
    nickname: str | None
    age: int | None
    gender: str | None
    preferred_gender: str | None
    interests: list[str]
    is_registered: bool
    is_banned: bool


class SessionMessageResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    sender_user_id: int
    message_type: str
    telegram_message_id: int
    text_content: str | None
    caption: str | None
    file_id: str | None
    created_at: datetime


class SessionDetailResponse(BaseModel):
    session_id: uuid.UUID
    status: str
    started_at: datetime
    ended_at: datetime | None
    end_reason: str | None
    user1: UserSummaryResponse
    user2: UserSummaryResponse
    messages: list[SessionMessageResponse]


class ReportResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    session_id: uuid.UUID
    reporter_user_id: int
    reported_user_id: int
    reason: str
    note: str | None
    created_at: datetime
