from __future__ import annotations

from fastapi import APIRouter, Request
from sqlalchemy import text


router = APIRouter()


@router.get("/healthz")
async def healthz() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/readyz")
async def readyz(request: Request) -> dict[str, str]:
    session_factory = request.app.state.session_factory
    redis = request.app.state.redis

    async with session_factory() as session:
        await session.execute(text("SELECT 1"))
    await redis.ping()
    return {"status": "ready"}

