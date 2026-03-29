from __future__ import annotations

import asyncio
from dataclasses import dataclass


class FakeLock:
    def __init__(self, lock: asyncio.Lock) -> None:
        self._lock = lock
        self._owned = False

    async def acquire(self) -> bool:
        await self._lock.acquire()
        self._owned = True
        return True

    async def release(self) -> None:
        if self._owned and self._lock.locked():
            self._lock.release()
        self._owned = False

    async def owned(self) -> bool:
        return self._owned


@dataclass
class FakeMessageResult:
    message_id: int


class FakeRedis:
    def __init__(self) -> None:
        self.counters: dict[str, int] = {}
        self.sets: dict[str, set[str]] = {}
        self.locks: dict[str, asyncio.Lock] = {}

    def lock(self, name: str, timeout: int, blocking_timeout: int | None = None) -> FakeLock:
        shared_lock = self.locks.setdefault(name, asyncio.Lock())
        return FakeLock(shared_lock)

    async def incr(self, key: str) -> int:
        value = self.counters.get(key, 0) + 1
        self.counters[key] = value
        return value

    async def expire(self, key: str, seconds: int) -> None:
        return None

    async def sadd(self, key: str, *values: object) -> None:
        bucket = self.sets.setdefault(key, set())
        for value in values:
            bucket.add(str(value))

    async def srem(self, key: str, *values: object) -> None:
        bucket = self.sets.setdefault(key, set())
        for value in values:
            bucket.discard(str(value))

    async def ping(self) -> bool:
        return True

    async def aclose(self) -> None:
        return None


class FakeBot:
    def __init__(self) -> None:
        self.sent_messages: list[dict[str, object]] = []
        self.copied_messages: list[dict[str, object]] = []
        self.documents: list[dict[str, object]] = []

    async def send_message(self, chat_id: int, text: str, reply_markup=None, **kwargs) -> FakeMessageResult:
        self.sent_messages.append(
            {
                "chat_id": chat_id,
                "text": text,
                "reply_markup": reply_markup,
                "kwargs": kwargs,
            }
        )
        return FakeMessageResult(message_id=len(self.sent_messages))

    async def copy_message(self, chat_id: int, from_chat_id: int, message_id: int, **kwargs) -> FakeMessageResult:
        self.copied_messages.append(
            {
                "chat_id": chat_id,
                "from_chat_id": from_chat_id,
                "message_id": message_id,
                "kwargs": kwargs,
            }
        )
        return FakeMessageResult(message_id=len(self.copied_messages))

    async def send_document(self, chat_id: int, document, caption: str | None = None, **kwargs) -> FakeMessageResult:
        self.documents.append(
            {
                "chat_id": chat_id,
                "document": document,
                "caption": caption,
                "kwargs": kwargs,
            }
        )
        return FakeMessageResult(message_id=len(self.documents))
