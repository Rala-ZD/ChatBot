from __future__ import annotations

from pydantic import BaseModel, Field


class ReportCreate(BaseModel):
    session_id: int
    reporter_user_id: int
    reported_user_id: int
    reason: str = Field(min_length=3, max_length=500)


class BanCreate(BaseModel):
    user_id: int
    banned_by: int
    reason: str = Field(min_length=3, max_length=500)

