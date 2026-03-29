from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.point_purchase import PointPurchase


class PointPurchaseRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(self, purchase: PointPurchase) -> PointPurchase:
        self.session.add(purchase)
        await self.session.flush()
        return purchase

    async def save(self, purchase: PointPurchase) -> PointPurchase:
        self.session.add(purchase)
        await self.session.flush()
        return purchase

    async def get_by_invoice_payload(self, invoice_payload: str) -> PointPurchase | None:
        result = await self.session.execute(
            select(PointPurchase).where(PointPurchase.invoice_payload == invoice_payload)
        )
        return result.scalar_one_or_none()

    async def get_by_invoice_payload_for_update(self, invoice_payload: str) -> PointPurchase | None:
        result = await self.session.execute(
            select(PointPurchase)
            .where(PointPurchase.invoice_payload == invoice_payload)
            .with_for_update()
        )
        return result.scalar_one_or_none()
