from __future__ import annotations

from contextlib import asynccontextmanager
from typing import AsyncIterator

from redis.asyncio import Redis


@asynccontextmanager
async def redis_lock(
    redis: Redis,
    name: str,
    timeout: int,
    blocking_timeout: int | None = None,
) -> AsyncIterator[None]:
    lock = redis.lock(name=name, timeout=timeout, blocking_timeout=blocking_timeout)
    acquired = await lock.acquire()
    if not acquired:
        raise TimeoutError(f"Could not acquire lock: {name}")
    try:
        yield
    finally:
        if await lock.owned():
            await lock.release()


class RedisRateLimiter:
    def __init__(self, redis: Redis, window_seconds: int) -> None:
        self.redis = redis
        self.window_seconds = window_seconds

    async def hit(self, key: str, limit: int) -> bool:
        current = await self.redis.incr(key)
        if current == 1:
            await self.redis.expire(key, self.window_seconds)
        return current <= limit
