from functools import lru_cache
import logging
from pathlib import Path
from typing import Annotated

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

SUPPORTED_LOG_FORMATS = {"text", "json"}


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
    auto_create_tables: bool = True
    clone_timeout_seconds: int = 120
    max_upload_size_bytes: int = 100 * 1024 * 1024

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


@lru_cache
def get_settings() -> Settings:
    return Settings()
