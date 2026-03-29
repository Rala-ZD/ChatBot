from __future__ import annotations

from functools import lru_cache

from pydantic import AnyUrl, Field, computed_field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    bot_token: str = Field(alias="BOT_TOKEN", min_length=20)
    webhook_base_url: AnyUrl = Field(alias="WEBHOOK_BASE_URL")
    webhook_secret: str = Field(alias="WEBHOOK_SECRET", min_length=12)
    webhook_path: str = Field(default="/webhook/telegram", alias="WEBHOOK_PATH")
    bot_delivery_mode: str = Field(default="polling", alias="BOT_DELIVERY_MODE")
    postgres_dsn: str = Field(alias="POSTGRES_DSN", min_length=1)
    redis_dsn: str = Field(alias="REDIS_DSN", min_length=1)
    ops_token: str | None = Field(default=None, alias="OPS_TOKEN")
    admin_channel_id: int = Field(alias="ADMIN_CHANNEL_ID")
    admin_user_ids: list[int] = Field(default_factory=list, alias="ADMIN_USER_IDS")
    minimum_age: int = Field(default=18, alias="MINIMUM_AGE", ge=13)
    support_username: str = Field(alias="SUPPORT_USERNAME", min_length=3)
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")
    app_host: str = Field(default="0.0.0.0", alias="APP_HOST")
    app_port: int = Field(default=8080, alias="APP_PORT", ge=1, le=65535)
    payments_enabled: bool = Field(default=False, alias="PAYMENTS_ENABLED")
    payments_currency: str = Field(default="XTR", alias="PAYMENTS_CURRENCY")
    points_package_10_xtr: int | None = Field(
        default=None,
        alias="POINTS_PACKAGE_10_XTR",
        ge=1,
    )
    points_package_50_xtr: int | None = Field(
        default=None,
        alias="POINTS_PACKAGE_50_XTR",
        ge=1,
    )
    points_package_150_xtr: int | None = Field(
        default=None,
        alias="POINTS_PACKAGE_150_XTR",
        ge=1,
    )
    match_scan_limit: int = Field(default=50, alias="MATCH_SCAN_LIMIT", ge=1, le=500)
    queue_lock_ttl: int = Field(default=15, alias="QUEUE_LOCK_TTL", ge=3, le=300)
    rate_limit_commands: int = Field(default=8, alias="RATE_LIMIT_COMMANDS", ge=1)
    rate_limit_messages: int = Field(default=25, alias="RATE_LIMIT_MESSAGES", ge=1)

    @field_validator("admin_user_ids", mode="before")
    @classmethod
    def parse_admin_ids(cls, value: object) -> list[int]:
        if value is None or value == "":
            return []
        if isinstance(value, list):
            return [int(item) for item in value]
        if isinstance(value, str):
            return [int(item.strip()) for item in value.split(",") if item.strip()]
        raise TypeError("ADMIN_USER_IDS must be a comma-separated string or a list")

    @field_validator("support_username")
    @classmethod
    def normalize_support_username(cls, value: str) -> str:
        return value.strip().removeprefix("@")

    @field_validator("log_level")
    @classmethod
    def uppercase_log_level(cls, value: str) -> str:
        return value.strip().upper()

    @field_validator("payments_currency", mode="before")
    @classmethod
    def normalize_payment_currency(cls, value: object) -> str:
        if value is None:
            return "XTR"
        if isinstance(value, str):
            cleaned = value.strip()
            return cleaned or "XTR"
        return str(value)

    @field_validator("payments_currency")
    @classmethod
    def uppercase_currency(cls, value: str) -> str:
        return value.upper()

    @field_validator("bot_delivery_mode", mode="before")
    @classmethod
    def normalize_delivery_mode(cls, value: object) -> str:
        if value is None:
            return "polling"
        return str(value).strip().lower() or "polling"

    @field_validator("bot_delivery_mode")
    @classmethod
    def validate_delivery_mode(cls, value: str) -> str:
        if value not in {"polling", "webhook"}:
            raise ValueError("BOT_DELIVERY_MODE must be either 'polling' or 'webhook'.")
        return value

    @field_validator("ops_token", mode="before")
    @classmethod
    def normalize_optional_secret(cls, value: object) -> str | None:
        if value is None:
            return None
        cleaned = str(value).strip()
        return cleaned or None

    @field_validator("webhook_path")
    @classmethod
    def normalize_webhook_path(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned.startswith("/"):
            cleaned = f"/{cleaned}"
        return cleaned.rstrip("/")

    @model_validator(mode="after")
    def validate_payments(self) -> "Settings":
        if not self.payments_enabled:
            return self

        missing: list[str] = []
        if self.payments_currency != "XTR":
            raise ValueError("PAYMENTS_CURRENCY must be XTR when PAYMENTS_ENABLED is true.")
        if self.points_package_10_xtr is None:
            missing.append("POINTS_PACKAGE_10_XTR")
        if self.points_package_50_xtr is None:
            missing.append("POINTS_PACKAGE_50_XTR")
        if self.points_package_150_xtr is None:
            missing.append("POINTS_PACKAGE_150_XTR")
        if missing:
            missing_text = ", ".join(missing)
            raise ValueError(f"Payment packages require these settings when PAYMENTS_ENABLED is true: {missing_text}")
        return self

    @computed_field  # type: ignore[misc]
    @property
    def webhook_secret_path(self) -> str:
        return f"{self.webhook_path}/{self.webhook_secret}"

    @computed_field  # type: ignore[misc]
    @property
    def webhook_url(self) -> str:
        return f"{str(self.webhook_base_url).rstrip('/')}{self.webhook_secret_path}"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
