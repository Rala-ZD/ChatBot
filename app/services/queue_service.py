from __future__ import annotations

import uuid
from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import Any

from redis.asyncio import Redis

from app.config import Settings
from app.db.models.user import User
from app.utils.time import utcnow


QUEUE_KEY = "queue:waiting"
USER_QUEUE_KEY = "queue:user:{user_id}"
MATCHMAKING_LOCK_KEY = "lock:matchmaking"
USER_LOCK_KEY = "lock:user:{user_id}"

RELEASE_LOCK_SCRIPT = """
if redis.call('get', KEYS[1]) == ARGV[1] then
    return redis.call('del', KEYS[1])
else
    return 0
end
"""


@dataclass(slots=True)
class RedisLock:
    redis: Redis
    key: str
    ttl: int
    token: str | None = None

    async def acquire(self) -> bool:
        token = uuid.uuid4().hex
        acquired = await self.redis.set(self.key, token, ex=self.ttl, nx=True)
        if acquired:
            self.token = token
        return bool(acquired)

    async def release(self) -> None:
        if self.token is None:
            return
        await self.redis.eval(RELEASE_LOCK_SCRIPT, 1, self.key, self.token)
        self.token = None


class QueueService:
    def __init__(self, redis: Redis, settings: Settings) -> None:
        self.redis = redis
        self.settings = settings

    @asynccontextmanager
    async def matchmaking_lock(self) -> Any:
        lock = RedisLock(self.redis, MATCHMAKING_LOCK_KEY, self.settings.queue_lock_ttl)
        acquired = await lock.acquire()
        try:
            yield acquired
        finally:
            if acquired:
                await lock.release()

    @asynccontextmanager
    async def user_lock(self, user_id: int) -> Any:
        lock = RedisLock(
            self.redis,
            USER_LOCK_KEY.format(user_id=user_id),
            self.settings.queue_lock_ttl,
        )
        acquired = await lock.acquire()
        try:
            yield acquired
        finally:
            if acquired:
                await lock.release()

    @asynccontextmanager
    async def multi_user_lock(self, user_ids: list[int] | tuple[int, ...]) -> Any:
        unique_user_ids = sorted(set(user_ids))
        locks = [
            RedisLock(
                self.redis,
                USER_LOCK_KEY.format(user_id=user_id),
                self.settings.queue_lock_ttl,
            )
            for user_id in unique_user_ids
        ]
        acquired_locks: list[RedisLock] = []
        try:
            for lock in locks:
                acquired = await lock.acquire()
                if not acquired:
                    yield False
                    return
                acquired_locks.append(lock)
            yield True
        finally:
            for lock in reversed(acquired_locks):
                await lock.release()

    async def enqueue_user(self, user: User) -> None:
        async with self.redis.pipeline(transaction=True) as pipe:
            pipe.zadd(QUEUE_KEY, {str(user.id): utcnow().timestamp()})
            pipe.hset(
                USER_QUEUE_KEY.format(user_id=user.id),
                mapping={
                    "user_id": str(user.id),
                    "gender": user.gender.value if user.gender else "",
                    "preferred_gender": user.preferred_gender.value if user.preferred_gender else "",
                },
            )
            await pipe.execute()

    async def remove_user(self, user_id: int) -> None:
        async with self.redis.pipeline(transaction=True) as pipe:
            pipe.zrem(QUEUE_KEY, str(user_id))
            pipe.delete(USER_QUEUE_KEY.format(user_id=user_id))
            await pipe.execute()

    async def is_queued(self, user_id: int) -> bool:
        score = await self.redis.zscore(QUEUE_KEY, str(user_id))
        return score is not None

    async def get_waiting_user_ids(self, limit: int) -> list[int]:
        user_ids = await self.redis.zrange(QUEUE_KEY, 0, max(limit - 1, 0))
        return [int(item) for item in user_ids]

    async def get_joined_timestamp(self, user_id: int) -> float | None:
        return await self.redis.zscore(QUEUE_KEY, str(user_id))
