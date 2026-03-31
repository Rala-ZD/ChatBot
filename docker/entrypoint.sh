#!/bin/sh
set -eu

python - <<'PY'
import asyncio
import os
import sys
from urllib.parse import urlparse

import asyncpg
from redis.asyncio import Redis


async def wait_for_postgres() -> None:
    dsn = os.environ["POSTGRES_DSN"].replace("+asyncpg", "")
    for attempt in range(30):
        try:
            conn = await asyncpg.connect(dsn=dsn)
            await conn.close()
            return
        except Exception:
            await asyncio.sleep(2)
    raise RuntimeError("Postgres did not become available in time.")


async def wait_for_redis() -> None:
    dsn = os.environ["REDIS_DSN"]
    redis = Redis.from_url(dsn, decode_responses=True)
    try:
        for attempt in range(30):
            try:
                await redis.ping()
                return
            except Exception:
                await asyncio.sleep(2)
        raise RuntimeError("Redis did not become available in time.")
    finally:
        await redis.aclose()


async def main() -> None:
    await wait_for_postgres()
    await wait_for_redis()


asyncio.run(main())
PY

alembic upgrade head
exec uvicorn app.main:app --host "${APP_HOST:-0.0.0.0}" --port "${APP_PORT:-8080}"
