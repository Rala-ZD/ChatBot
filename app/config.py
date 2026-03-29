from __future__ import annotations

from functools import lru_cache
from typing import Any

from pydantic import AnyHttpUrl, Field, SecretStr, computed_field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    app_name: str = "Anonymous Stranger Chat Bot"
    environment: str = "production"

    bot_token: SecretStr = Field(alias="BOT_TOKEN")
    webhook_base_url: AnyHttpUrl = Field(alias="WEBHOOK_BASE_URL")
    webhook_secret: SecretStr = Field(alias="WEBHOOK_SECRET")
    webhook_path: str = "/telegram/webhook"

    postgres_dsn: str = Field(alias="POSTGRES_DSN")
    redis_dsn: str = Field(alias="REDIS_DSN")

    admin_channel_id: int = Field(alias="ADMIN_CHANNEL_ID")
    minimum_age: int = Field(default=18, alias="MINIMUM_AGE")
    support_username: str = Field(alias="SUPPORT_USERNAME")
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")

    admin_user_ids_raw: str = Field(default="", alias="ADMIN_USER_IDS")
    admin_api_token: SecretStr = Field(alias="ADMIN_API_TOKEN")

    match_soft_preference_after_seconds: int = Field(
        default=90,
        alias="MATCH_SOFT_PREFERENCE_AFTER_SECONDS",
    )
    command_rate_limit: int = Field(default=30, alias="COMMAND_RATE_LIMIT")
    message_rate_limit: int = Field(default=45, alias="MESSAGE_RATE_LIMIT")
    rate_limit_window_seconds: int = Field(default=60, alias="RATE_LIMIT_WINDOW_SECONDS")
    profile_nickname_max_length: int = Field(default=32, alias="PROFILE_NICKNAME_MAX_LENGTH")
    profile_interests_max_count: int = Field(default=8, alias="PROFILE_INTERESTS_MAX_COUNT")
    profile_interest_max_length: int = Field(default=24, alias="PROFILE_INTEREST_MAX_LENGTH")
    max_report_note_length: int = Field(default=300, alias="MAX_REPORT_NOTE_LENGTH")
    consent_version: str = Field(default="2026-03", alias="CONSENT_VERSION")

    match_lock_seconds: int = Field(default=10, alias="MATCH_LOCK_SECONDS")
    session_relay_lock_seconds: int = Field(default=5, alias="SESSION_RELAY_LOCK_SECONDS")
    export_lock_seconds: int = Field(default=10, alias="EXPORT_LOCK_SECONDS")
    webhook_drop_pending_updates: bool = Field(default=False, alias="WEBHOOK_DROP_PENDING_UPDATES")

    @field_validator("minimum_age")
    @classmethod
    def validate_minimum_age(cls, value: int) -> int:
        if value < 13:
            raise ValueError("MINIMUM_AGE must be at least 13.")
        return value

    @field_validator("support_username")
    @classmethod
    def normalize_support_username(cls, value: str) -> str:
        return value.lstrip("@")

    @field_validator("log_level")
    @classmethod
    def normalize_log_level(cls, value: str) -> str:
        return value.upper()

    @computed_field  # type: ignore[misc]
    @property
    def admin_user_ids(self) -> list[int]:
        if not self.admin_user_ids_raw.strip():
            return []
        return [
            int(chunk.strip())
            for chunk in self.admin_user_ids_raw.split(",")
            if chunk.strip()
        ]

    @computed_field  # type: ignore[misc]
    @property
    def webhook_url(self) -> str:
        return f"{str(self.webhook_base_url).rstrip('/')}{self.webhook_path}"

    def is_admin(self, telegram_id: int) -> bool:
        return telegram_id in self.admin_user_ids

    def redact(self, value: str | SecretStr) -> str:
        if isinstance(value, SecretStr):
            return value.get_secret_value()[:4] + "***"
        if len(value) <= 4:
            return "***"
        return value[:4] + "***"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()


def settings_as_log_context(settings: Settings) -> dict[str, Any]:
    return {
        "app_name": settings.app_name,
        "environment": settings.environment,
        "webhook_url": settings.webhook_url,
        "admin_channel_id": settings.admin_channel_id,
    }
