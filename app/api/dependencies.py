from __future__ import annotations

import secrets

from fastapi import Depends, Header, HTTPException, Request, status

from app.config import Settings
from app.services.container import ServiceContainer


def get_services(request: Request) -> ServiceContainer:
    return request.app.state.services


def get_settings(request: Request) -> Settings:
    return request.app.state.settings


def require_admin_token(
    authorization: str | None = Header(default=None),
    settings: Settings = Depends(get_settings),
) -> None:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unauthorized")
    provided = authorization.removeprefix("Bearer ").strip()
    expected = settings.admin_api_token.get_secret_value()
    if not secrets.compare_digest(provided, expected):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unauthorized")
