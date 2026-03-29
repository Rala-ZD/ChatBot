from __future__ import annotations

from fastapi import APIRouter, Header, HTTPException, Request, status


router = APIRouter()


@router.get("/ops/stats")
async def ops_stats(
    request: Request,
    x_ops_token: str | None = Header(default=None, alias="X-Ops-Token"),
) -> dict[str, int | float | str]:
    settings = request.app.state.settings
    if not settings.ops_token:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Ops stats are disabled.",
        )
    if x_ops_token != settings.ops_token:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")

    ops_service = request.app.state.ops_service
    return await ops_service.get_stats()
