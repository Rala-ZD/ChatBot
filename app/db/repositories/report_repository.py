from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.report import Report


class ReportRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(self, report: Report) -> Report:
        self.session.add(report)
        await self.session.flush()
        return report

