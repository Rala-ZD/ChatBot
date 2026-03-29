from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import text

from app.api.dependencies import get_services
from app.schemas.api import HealthResponse
from app.services.container import ServiceContainer

router = APIRouter(prefix="/health", tags=["health"])


@router.get("/live", response_model=HealthResponse)
async def live() -> HealthResponse:
    return HealthResponse(status="ok", service="live")


@router.get("/ready", response_model=HealthResponse)
async def ready(services: ServiceContainer = Depends(get_services)) -> HealthResponse:
    async with services.session_factory() as session:
        await session.execute(text("SELECT 1"))
    await services.redis.ping()
    return HealthResponse(status="ok", service="ready")
