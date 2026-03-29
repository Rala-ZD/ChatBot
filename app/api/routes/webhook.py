from __future__ import annotations

import secrets

from aiogram.types import Update
from fastapi import APIRouter, Depends, Header, HTTPException, Request, status

from app.api.dependencies import get_services, get_settings
from app.config import Settings
from app.services.container import ServiceContainer

router = APIRouter(tags=["webhook"])


@router.post("/telegram/webhook", status_code=status.HTTP_200_OK)
async def telegram_webhook(
    request: Request,
    services: ServiceContainer = Depends(get_services),
    settings: Settings = Depends(get_settings),
    secret_token: str | None = Header(default=None, alias="X-Telegram-Bot-Api-Secret-Token"),
) -> dict[str, bool]:
    expected = settings.webhook_secret.get_secret_value()
    if not secret_token or not secrets.compare_digest(secret_token, expected):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid webhook secret")

    payload = await request.json()
    update = Update.model_validate(payload)
    await request.app.state.dispatcher.feed_webhook_update(request.app.state.bot, update)
    return {"ok": True}
