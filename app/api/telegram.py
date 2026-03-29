from __future__ import annotations

from fastapi import APIRouter, Header, HTTPException, Request, status
from aiogram.types import Update


router = APIRouter()


@router.post("/{secret}")
async def telegram_webhook(
    secret: str,
    request: Request,
    x_telegram_bot_api_secret_token: str | None = Header(
        default=None,
        alias="X-Telegram-Bot-Api-Secret-Token",
    ),
) -> dict[str, bool]:
    settings = request.app.state.settings
    if settings.bot_delivery_mode != "webhook":
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
    if secret != settings.webhook_secret:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
    if x_telegram_bot_api_secret_token != settings.webhook_secret:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")

    payload = await request.json()
    bot = request.app.state.bot
    dispatcher = request.app.state.dispatcher
    update = Update.model_validate(payload, context={"bot": bot})
    await dispatcher.feed_update(bot, update)
    return {"ok": True}
