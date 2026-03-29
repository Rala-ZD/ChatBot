from __future__ import annotations

from pydantic import BaseModel


class MatchOutcome(BaseModel):
    status: str
    session_id: int | None = None
    partner_user_id: int | None = None

