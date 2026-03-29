from __future__ import annotations

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.config import Settings
from app.db.base import Base
from app.services.container import ServiceContainer
from tests.fixtures.fakes import FakeBot, FakeRedis


@pytest.fixture
def settings() -> Settings:
    return Settings.model_validate(
        {
            "BOT_TOKEN": "123456:TEST",
            "WEBHOOK_BASE_URL": "https://example.com",
            "WEBHOOK_SECRET": "secret-token",
            "POSTGRES_DSN": "sqlite+aiosqlite:///:memory:",
            "REDIS_DSN": "redis://localhost:6379/0",
            "ADMIN_CHANNEL_ID": -1001234567890,
            "MINIMUM_AGE": 18,
            "SUPPORT_USERNAME": "support_account",
            "LOG_LEVEL": "INFO",
            "ADMIN_API_TOKEN": "internal-api-token",
            "ADMIN_USER_IDS": "1,2",
        }
    )


@pytest_asyncio.fixture
async def session_factory():
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        poolclass=StaticPool,
        connect_args={"check_same_thread": False},
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    factory = async_sessionmaker(engine, expire_on_commit=False)
    try:
        yield factory
    finally:
        await engine.dispose()


@pytest.fixture
def fake_redis() -> FakeRedis:
    return FakeRedis()


@pytest.fixture
def fake_bot() -> FakeBot:
    return FakeBot()


@pytest.fixture
def services(
    session_factory,
    fake_redis: FakeRedis,
    fake_bot: FakeBot,
    settings: Settings,
) -> ServiceContainer:
    return ServiceContainer(session_factory, fake_redis, fake_bot, settings)
