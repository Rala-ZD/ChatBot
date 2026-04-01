from __future__ import annotations

from types import SimpleNamespace

from aiogram.fsm.storage.base import DefaultKeyBuilder, StorageKey
from aiogram.fsm.storage.redis import RedisStorage
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.ops import router as ops_router
from app.api.telegram import router as telegram_router
from app.bot.dispatcher import create_dispatcher
from app.services.ops_service import OpsService

from tests.conftest import FakeRedis


class FakeDispatcher:
    def __init__(self) -> None:
        self.feed_calls: list[tuple[object, object]] = []

    async def feed_update(self, bot: object, update: object) -> None:
        self.feed_calls.append((bot, update))


def _webhook_payload() -> dict[str, object]:
    return {
        "update_id": 1,
        "message": {
            "message_id": 10,
            "date": 1,
            "chat": {"id": 1001, "type": "private"},
            "from": {"id": 1001, "is_bot": False, "first_name": "Test"},
            "text": "/start",
        },
    }


def test_dispatcher_uses_redis_storage(settings) -> None:
    dispatcher = create_dispatcher(
        settings,
        session_factory=SimpleNamespace(),
        redis=FakeRedis(),
        bot=SimpleNamespace(),
    )

    assert isinstance(dispatcher.storage, RedisStorage)


def test_fsm_storage_keys_are_scoped_per_user() -> None:
    builder = DefaultKeyBuilder(with_bot_id=True, with_destiny=True)

    first_key = builder.build(
        StorageKey(bot_id=1, chat_id=10, user_id=1001),
        part="data",
    )
    second_key = builder.build(
        StorageKey(bot_id=1, chat_id=10, user_id=1002),
        part="data",
    )

    assert first_key != second_key


def test_webhook_route_accepts_updates_in_webhook_mode(settings) -> None:
    app = FastAPI()
    dispatcher = FakeDispatcher()
    bot = object()
    app.state.settings = settings.model_copy(update={"bot_delivery_mode": "webhook"})
    app.state.dispatcher = dispatcher
    app.state.bot = bot
    app.include_router(telegram_router, prefix=settings.webhook_path)

    client = TestClient(app)
    response = client.post(
        f"{settings.webhook_path}/{settings.webhook_secret}",
        headers={"X-Telegram-Bot-Api-Secret-Token": settings.webhook_secret},
        json=_webhook_payload(),
    )

    assert response.status_code == 200
    assert response.json() == {"ok": True}
    assert len(dispatcher.feed_calls) == 1
    assert dispatcher.feed_calls[0][0] is bot


def test_webhook_route_is_disabled_in_polling_mode(settings) -> None:
    app = FastAPI()
    app.state.settings = settings.model_copy(update={"bot_delivery_mode": "polling"})
    app.state.dispatcher = FakeDispatcher()
    app.state.bot = object()
    app.include_router(telegram_router, prefix=settings.webhook_path)

    client = TestClient(app)
    response = client.post(
        f"{settings.webhook_path}/{settings.webhook_secret}",
        headers={"X-Telegram-Bot-Api-Secret-Token": settings.webhook_secret},
        json=_webhook_payload(),
    )

    assert response.status_code == 404


def test_ops_stats_endpoint_requires_token_and_returns_snapshot(settings) -> None:
    redis = FakeRedis()
    ops_service = OpsService(redis, settings.model_copy(update={"bot_delivery_mode": "webhook"}))
    app = FastAPI()
    app.state.settings = settings
    app.state.ops_service = ops_service
    app.include_router(ops_router)

    import asyncio

    asyncio.run(redis.zadd("queue:waiting", {"1": 1.0, "2": 2.0}))
    asyncio.run(ops_service.record_search_start())
    asyncio.run(ops_service.record_search_start())
    asyncio.run(ops_service.record_cancel())
    asyncio.run(ops_service.record_match_created(12))
    asyncio.run(ops_service.record_payment_success())

    client = TestClient(app)
    forbidden = client.get("/ops/stats", headers={"X-Ops-Token": "wrong-token"})
    success = client.get("/ops/stats", headers={"X-Ops-Token": settings.ops_token})

    assert forbidden.status_code == 403
    assert success.status_code == 200
    assert success.json() == {
        "delivery_mode": "webhook",
        "active_searching_users": 2,
        "search_starts": 2,
        "cancels": 1,
        "matches_created": 1,
        "total_wait_seconds": 12,
        "average_wait_seconds": 12.0,
        "cancel_rate": 0.5,
        "failed_handlers": 0,
        "payment_success_count": 1,
    }
