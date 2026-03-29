from __future__ import annotations

import pytest

from app.bot.middlewares.error_handler import ErrorHandlerMiddleware

from tests.conftest import FakeOpsService


@pytest.mark.asyncio
async def test_error_handler_records_failed_handler_metric() -> None:
    ops_service = FakeOpsService()
    middleware = ErrorHandlerMiddleware(ops_service)

    async def failing_handler(event, data):
        raise RuntimeError("boom")

    result = await middleware(failing_handler, object(), {})

    assert result is None
    assert ops_service.failed_handlers == 1
