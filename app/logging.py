from __future__ import annotations

import logging
import sys
from typing import Any

import structlog


REDACTED_KEYS = {"authorization", "bot_token", "token", "webhook_secret"}


def _redact_value(_: Any, __: str, event_dict: dict[str, Any]) -> dict[str, Any]:
    for key in tuple(event_dict.keys()):
        if key.lower() in REDACTED_KEYS:
            event_dict[key] = "***redacted***"
    return event_dict


def configure_logging(level: str) -> None:
    timestamper = structlog.processors.TimeStamper(fmt="iso", utc=True)

    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            timestamper,
            _redact_value,
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.JSONRenderer(),
        ],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )

    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format="%(message)s",
        stream=sys.stdout,
    )


def get_logger(name: str | None = None) -> structlog.stdlib.BoundLogger:
    return structlog.get_logger(name)

