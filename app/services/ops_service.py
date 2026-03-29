from __future__ import annotations

from redis.asyncio import Redis

from app.config import Settings
from app.services.queue_service import QUEUE_KEY


SEARCH_STARTS_KEY = "ops:search_starts"
CANCELS_KEY = "ops:cancels"
MATCHES_CREATED_KEY = "ops:matches_created"
TOTAL_WAIT_SECONDS_KEY = "ops:total_wait_seconds"
FAILED_HANDLERS_KEY = "ops:failed_handlers"
PAYMENT_SUCCESS_COUNT_KEY = "ops:payment_success_count"


class OpsService:
    def __init__(self, redis: Redis, settings: Settings) -> None:
        self.redis = redis
        self.settings = settings

    async def record_search_start(self) -> None:
        await self.redis.incr(SEARCH_STARTS_KEY)

    async def record_cancel(self) -> None:
        await self.redis.incr(CANCELS_KEY)

    async def record_match_created(self, average_wait_seconds: int) -> None:
        async with self.redis.pipeline(transaction=True) as pipe:
            pipe.incr(MATCHES_CREATED_KEY)
            pipe.incrby(TOTAL_WAIT_SECONDS_KEY, max(average_wait_seconds, 0))
            await pipe.execute()

    async def record_handler_failure(self) -> None:
        await self.redis.incr(FAILED_HANDLERS_KEY)

    async def record_payment_success(self) -> None:
        await self.redis.incr(PAYMENT_SUCCESS_COUNT_KEY)

    async def get_stats(self) -> dict[str, int | float | str]:
        search_starts, cancels, matches_created, total_wait_seconds, failed_handlers, payment_success_count = (
            await self.redis.mget(
                SEARCH_STARTS_KEY,
                CANCELS_KEY,
                MATCHES_CREATED_KEY,
                TOTAL_WAIT_SECONDS_KEY,
                FAILED_HANDLERS_KEY,
                PAYMENT_SUCCESS_COUNT_KEY,
            )
        )
        active_searching = await self.redis.zcard(QUEUE_KEY)
        search_start_count = int(search_starts or 0)
        cancel_count = int(cancels or 0)
        match_count = int(matches_created or 0)
        wait_total = int(total_wait_seconds or 0)

        average_wait = round(wait_total / match_count, 2) if match_count else 0.0
        cancel_rate = round(cancel_count / search_start_count, 4) if search_start_count else 0.0

        return {
            "delivery_mode": self.settings.bot_delivery_mode,
            "active_searching_users": int(active_searching),
            "search_starts": search_start_count,
            "cancels": cancel_count,
            "matches_created": match_count,
            "total_wait_seconds": wait_total,
            "average_wait_seconds": average_wait,
            "cancel_rate": cancel_rate,
            "failed_handlers": int(failed_handlers or 0),
            "payment_success_count": int(payment_success_count or 0),
        }
