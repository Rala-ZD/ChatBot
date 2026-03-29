from __future__ import annotations

import uuid

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Report


class ReportRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(
        self,
        *,
        session_id: uuid.UUID,
        reporter_user_id: int,
        reported_user_id: int,
        reason: str,
        note: str | None,
    ) -> Report:
        report = Report(
            session_id=session_id,
            reporter_user_id=reporter_user_id,
            reported_user_id=reported_user_id,
            reason=reason,
            note=note,
        )
        self.session.add(report)
        await self.session.flush()
        return report

    async def list_recent(self, limit: int = 50) -> list[Report]:
        result = await self.session.execute(
            select(Report).order_by(desc(Report.created_at), desc(Report.id)).limit(limit)
        )
        return list(result.scalars().all())
