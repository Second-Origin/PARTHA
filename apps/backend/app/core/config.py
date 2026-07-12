import logging
from functools import lru_cache
from pathlib import Path
from typing import Annotated
from urllib.parse import urlparse

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

SUPPORTED_LOG_FORMATS = {"text", "json"}

# 32 chars ~= 256 bits from a token_urlsafe/hex secret, the floor for an HS256
# signing key. Enforced outside development/test only, so local work is not
# blocked by a short throwaway value.
AUTH_SECRET_MIN_LENGTH = 32


class Settings(BaseSettings):
    app_name: str = "PARTHA Backend"
    app_env: str = "development"
    log_level: str = "INFO"
    log_format: str = "text"
    database_url: str = "sqlite:///./.local/partha.db"
    redis_url: str = "redis://localhost:6379/0"
    storage_path: Path = Path("./.local/storage")
    cors_origins: Annotated[list[str], NoDecode] = Field(
        default_factory=lambda: ["http://localhost:5173", "http://127.0.0.1:5173"]
    )
    # Tri-state: when AUTO_CREATE_TABLES is not set explicitly, it resolves to
    # True only for development/test and False otherwise (production/staging),
    # so non-dev deployments rely on Alembic migrations rather than create_all.
    # An explicit env value always wins.
    auto_create_tables: bool | None = None
    # Signs access tokens (HS256). Empty is tolerated only in development/test,
    # where a fixed insecure value is substituted; staging/production refuse to
    # start without an explicit secret.
    auth_secret_key: str = ""
    access_token_ttl_seconds: int = 900
    refresh_token_ttl_seconds: int = 14 * 24 * 60 * 60
    clone_timeout_seconds: int = 120
    max_upload_size_bytes: int = 100 * 1024 * 1024
    max_clone_size_bytes: int = 500 * 1024 * 1024

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    @field_validator("cors_origins", mode="before")
    @classmethod
    def parse_cors_origins(cls, value: str | list[str]) -> list[str]:
        if isinstance(value, str):
            return [origin.strip() for origin in value.split(",") if origin.strip()]
        return value

    @field_validator("app_env")
    @classmethod
    def validate_app_env(cls, value: str) -> str:
        normalized = value.lower()
        if normalized not in {"development", "test", "staging", "production"}:
            raise ValueError(f"Unsupported app environment: {value}")
        return normalized

    @field_validator("log_level")
    @classmethod
    def validate_log_level(cls, value: str) -> str:
        normalized = value.upper()
        if normalized not in logging.getLevelNamesMapping():
            raise ValueError(f"Unsupported log level: {value}")
        return normalized

    @field_validator("log_format")
    @classmethod
    def validate_log_format(cls, value: str) -> str:
        normalized = value.lower()
        if normalized not in SUPPORTED_LOG_FORMATS:
            raise ValueError(f"Unsupported log format: {value}")
        return normalized

    @field_validator("database_url")
    @classmethod
    def validate_database_url(cls, value: str) -> str:
        parsed = urlparse(value)
        if not parsed.scheme:
            raise ValueError("DATABASE_URL must include a scheme.")
        if parsed.scheme not in {"sqlite", "postgresql+psycopg", "postgresql"}:
            raise ValueError(f"Unsupported database URL scheme: {parsed.scheme}")
        return value

    @field_validator("redis_url")
    @classmethod
    def validate_redis_url(cls, value: str) -> str:
        parsed = urlparse(value)
        if parsed.scheme not in {"redis", "rediss"}:
            raise ValueError(f"Unsupported Redis URL scheme: {parsed.scheme}")
        return value

    @field_validator("cors_origins")
    @classmethod
    def validate_cors_origins(cls, value: list[str]) -> list[str]:
        if not value:
            raise ValueError("At least one CORS origin must be configured.")
        for origin in value:
            parsed = urlparse(origin)
            if parsed.scheme not in {"http", "https"} or not parsed.netloc:
                raise ValueError(f"Invalid CORS origin: {origin}")
        return value

    @field_validator(
        "clone_timeout_seconds",
        "max_upload_size_bytes",
        "max_clone_size_bytes",
        "access_token_ttl_seconds",
        "refresh_token_ttl_seconds",
    )
    @classmethod
    def validate_positive_int(cls, value: int) -> int:
        if value <= 0:
            raise ValueError("Value must be greater than zero.")
        return value

    @model_validator(mode="after")
    def resolve_auto_create_tables(self) -> "Settings":
        if self.auto_create_tables is None:
            self.auto_create_tables = self.app_env in {"development", "test"}
        return self

    @model_validator(mode="after")
    def resolve_auth_secret_key(self) -> "Settings":
        lenient = self.app_env in {"development", "test"}
        if not self.auth_secret_key:
            if not lenient:
                raise ValueError("AUTH_SECRET_KEY must be set outside development/test environments.")
            self.auth_secret_key = "insecure-dev-secret-do-not-use-in-production"
        elif not lenient and len(self.auth_secret_key) < AUTH_SECRET_MIN_LENGTH:
            raise ValueError(
                f"AUTH_SECRET_KEY must be at least {AUTH_SECRET_MIN_LENGTH} characters "
                "outside development/test environments."
            )
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
