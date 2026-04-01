from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from datetime import timedelta
from typing import Any

import pytest
from aiogram.exceptions import TelegramBadRequest
from aiogram.methods import DeleteMessage

from app.config import Settings
from app.db.models.user import User
from app.utils.enums import Gender, PreferredGender
from app.utils.referral import generate_referral_code
from app.utils.time import utcnow


class FakeSession:
    def __init__(self) -> None:
        self.commits = 0
        self.rollbacks = 0

    async def commit(self) -> None:
        self.commits += 1

    async def rollback(self) -> None:
        self.rollbacks += 1


class FakeRedisPipeline:
    def __init__(self, redis: "FakeRedis") -> None:
        self.redis = redis
        self.operations: list[tuple[str, tuple[Any, ...], dict[str, Any]]] = []

    async def __aenter__(self) -> "FakeRedisPipeline":
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        return None

    def incr(self, key: str) -> "FakeRedisPipeline":
        self.operations.append(("incr", (key,), {}))
        return self

    def incrby(self, key: str, amount: int) -> "FakeRedisPipeline":
        self.operations.append(("incrby", (key, amount), {}))
        return self

    def zadd(self, key: str, mapping: dict[str, float]) -> "FakeRedisPipeline":
        self.operations.append(("zadd", (key, mapping), {}))
        return self

    def hset(self, key: str, mapping: dict[str, str]) -> "FakeRedisPipeline":
        self.operations.append(("hset", (key,), {"mapping": mapping}))
        return self

    def zrem(self, key: str, member: str) -> "FakeRedisPipeline":
        self.operations.append(("zrem", (key, member), {}))
        return self

    def delete(self, key: str) -> "FakeRedisPipeline":
        self.operations.append(("delete", (key,), {}))
        return self

    async def execute(self) -> list[Any]:
        results: list[Any] = []
        for operation, args, kwargs in self.operations:
            method = getattr(self.redis, operation)
            results.append(await method(*args, **kwargs))
        self.operations.clear()
        return results


class FakeRedis:
    def __init__(self) -> None:
        self.values: dict[str, str] = {}
        self.hashes: dict[str, dict[str, str]] = {}
        self.sorted_sets: dict[str, dict[str, float]] = {}

    async def set(self, key: str, value: str, *, ex: int | None = None, nx: bool = False) -> bool:
        if nx and key in self.values:
            return False
        self.values[key] = value
        return True

    async def get(self, key: str) -> str | None:
        return self.values.get(key)

    async def delete(self, key: str) -> int:
        removed = 1 if key in self.values or key in self.hashes else 0
        self.values.pop(key, None)
        self.hashes.pop(key, None)
        return removed

    async def incr(self, key: str) -> int:
        current = int(self.values.get(key, "0")) + 1
        self.values[key] = str(current)
        return current

    async def incrby(self, key: str, amount: int) -> int:
        current = int(self.values.get(key, "0")) + amount
        self.values[key] = str(current)
        return current

    async def mget(self, *keys: str) -> list[str | None]:
        return [self.values.get(key) for key in keys]

    async def zadd(self, key: str, mapping: dict[str, float]) -> int:
        bucket = self.sorted_sets.setdefault(key, {})
        for member, score in mapping.items():
            bucket[member] = score
        return len(mapping)

    async def zrem(self, key: str, member: str) -> int:
        bucket = self.sorted_sets.get(key, {})
        existed = member in bucket
        bucket.pop(member, None)
        return int(existed)

    async def zscore(self, key: str, member: str) -> float | None:
        return self.sorted_sets.get(key, {}).get(member)

    async def zrange(self, key: str, start: int, end: int) -> list[str]:
        items = sorted(self.sorted_sets.get(key, {}).items(), key=lambda item: item[1])
        if end == -1:
            sliced = items[start:]
        else:
            sliced = items[start : end + 1]
        return [member for member, _ in sliced]

    async def zcard(self, key: str) -> int:
        return len(self.sorted_sets.get(key, {}))

    async def hset(self, key: str, *, mapping: dict[str, str]) -> int:
        self.hashes[key] = dict(mapping)
        return len(mapping)

    def pipeline(self, transaction: bool = True) -> FakeRedisPipeline:
        return FakeRedisPipeline(self)

    async def ping(self) -> bool:
        return True

    async def aclose(self) -> None:
        return None


class FakeOpsService:
    def __init__(self) -> None:
        self.search_starts = 0
        self.cancels = 0
        self.matches_created = 0
        self.wait_totals: list[int] = []
        self.failed_handlers = 0
        self.payment_successes = 0

    async def record_search_start(self) -> None:
        self.search_starts += 1

    async def record_cancel(self) -> None:
        self.cancels += 1

    async def record_match_created(self, average_wait_seconds: int) -> None:
        self.matches_created += 1
        self.wait_totals.append(average_wait_seconds)

    async def record_handler_failure(self) -> None:
        self.failed_handlers += 1

    async def record_payment_success(self) -> None:
        self.payment_successes += 1


@dataclass
class FakeSentMessage:
    message_id: int


@dataclass
class FakeBotMessage:
    chat_id: int
    text: str
    reply_markup: object | None = None


class FakeBot:
    def __init__(self) -> None:
        self.messages: list[tuple[int, str]] = []
        self.message_payloads: list[FakeBotMessage] = []
        self.copied_messages: list[tuple[int, int, int]] = []
        self.deleted_messages: list[tuple[int, int]] = []
        self.fail_delete = False

    async def send_message(self, chat_id: int, text: str, **kwargs: object) -> FakeSentMessage:
        self.messages.append((chat_id, text))
        self.message_payloads.append(
            FakeBotMessage(
                chat_id=chat_id,
                text=text,
                reply_markup=kwargs.get("reply_markup"),
            )
        )
        return FakeSentMessage(message_id=len(self.messages))

    async def copy_message(self, chat_id: int, from_chat_id: int, message_id: int, **_: object) -> FakeSentMessage:
        self.copied_messages.append((chat_id, from_chat_id, message_id))
        return FakeSentMessage(message_id=len(self.copied_messages))

    async def delete_message(self, chat_id: int, message_id: int) -> bool:
        self.deleted_messages.append((chat_id, message_id))
        if self.fail_delete:
            raise TelegramBadRequest(
                DeleteMessage(chat_id=chat_id, message_id=message_id),
                "message can't be deleted",
            )
        return True


@pytest.fixture()
def settings() -> Settings:
    return Settings(
        _env_file=None,
        BOT_TOKEN="1234567890:abcdefghijklmnopqrstuvwxyz",
        WEBHOOK_BASE_URL="https://example.com",
        WEBHOOK_SECRET="super-secret-token",
        WEBHOOK_PATH="/webhook/telegram",
        BOT_DELIVERY_MODE="polling",
        POSTGRES_DSN="postgresql+asyncpg://postgres:postgres@localhost:5432/chatbot",
        REDIS_DSN="redis://localhost:6379/0",
        OPS_TOKEN="ops-secret-token",
        ADMIN_CHANNEL_ID=-1001234567890,
        ADMIN_USER_IDS="1,2",
        MINIMUM_AGE=18,
        SUPPORT_USERNAME="supportdesk",
        LOG_LEVEL="INFO",
        PAYMENTS_ENABLED=False,
    )


def build_user(
    user_id: int,
    *,
    telegram_id: int | None = None,
    gender: Gender | str = Gender.OTHER,
    preferred_gender: PreferredGender | str = PreferredGender.ANY,
    is_registered: bool = True,
    is_banned: bool = False,
    referral_code: str | None = None,
    referred_by_user_id: int | None = None,
    points_balance: int = 0,
    rating_score: Decimal | str | None = "5.0",
    interests: list[str] | None = None,
    vip_active: bool = False,
) -> User:
    return User(
        id=user_id,
        telegram_id=telegram_id or (1000 + user_id),
        first_name=f"User{user_id}",
        username=f"user{user_id}",
        referral_code=referral_code or generate_referral_code(),
        referred_by_user_id=referred_by_user_id,
        points_balance=points_balance,
        rating_score=Decimal(str(rating_score)) if rating_score is not None else Decimal("5.0"),
        vip_until=utcnow() + timedelta(days=1) if vip_active else None,
        age=25,
        gender=Gender(gender),
        preferred_gender=PreferredGender(preferred_gender),
        interests_json=interests or [],
        is_registered=is_registered,
        is_banned=is_banned,
    )
