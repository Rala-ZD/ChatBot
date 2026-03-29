from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, status

from app.api.dependencies import get_services, require_admin_token
from app.schemas.api import BanRequest, ReportResponse, SessionDetailResponse
from app.services.container import ServiceContainer

router = APIRouter(
    prefix="/admin",
    tags=["admin"],
    dependencies=[Depends(require_admin_token)],
)


@router.get("/reports", response_model=list[ReportResponse])
async def list_reports(
    limit: int = 50,
    services: ServiceContainer = Depends(get_services),
) -> list[ReportResponse]:
    return await services.admin_service.list_reports(limit=limit)


@router.get("/sessions/{session_id}", response_model=SessionDetailResponse)
async def get_session_detail(
    session_id: uuid.UUID,
    services: ServiceContainer = Depends(get_services),
) -> SessionDetailResponse:
    return await services.admin_service.get_session_detail(session_id)


@router.post("/users/{user_id}/ban", status_code=status.HTTP_204_NO_CONTENT)
async def ban_user(
    user_id: int,
    payload: BanRequest,
    services: ServiceContainer = Depends(get_services),
) -> None:
    await services.moderation_service.ban_user(
        user_id=user_id,
        reason=payload.reason,
        banned_by=0,
    )


@router.delete("/users/{user_id}/ban", status_code=status.HTTP_204_NO_CONTENT)
async def unban_user(
    user_id: int,
    services: ServiceContainer = Depends(get_services),
) -> None:
    await services.moderation_service.unban_user(
        user_id=user_id,
        revoked_by=0,
    )
