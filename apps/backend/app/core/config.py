import base64
import binascii
import hashlib
import ipaddress
import logging
from functools import lru_cache
from pathlib import Path
from typing import Annotated
from urllib.parse import urlparse

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

from app.core.ai_egress import DestinationPolicyError, normalize_base_url

SUPPORTED_LOG_FORMATS = {"text", "json"}

# 32 chars ~= 256 bits from a token_urlsafe/hex secret, the floor for an HS256
# signing key. Enforced outside development/test only, so local work is not
# blocked by a short throwaway value.
AUTH_SECRET_MIN_LENGTH = 32

# A Fernet key is the URL-safe base64 encoding of exactly 32 random bytes. The
# development/test default is derived deterministically so local work needs no
# configuration, but it is never used outside those environments — staging and
# production must supply their own key or refuse to start.
FERNET_KEY_BYTES = 32
_DEV_AI_ENCRYPTION_KEY = base64.urlsafe_b64encode(
    hashlib.sha256(b"partha-dev-provider-encryption-key").digest()
).decode()


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
    # Fernet key (URL-safe base64 of 32 bytes) that encrypts each user's AI
    # provider API keys at rest. Empty is tolerated only in development/test,
    # where a fixed derived key is substituted; staging/production refuse to
    # start without an explicit key so secrets are never stored under a shared
    # well-known key.
    ai_encryption_key: str = ""
    # Fixed-window request budgets per identity (client IP until per-user
    # keying lands with auth enforcement). "memory" is per-process and
    # deterministic — right for tests/dev; Compose overrides to "redis" so
    # budgets are shared across workers.
    rate_limit_enabled: bool = True
    rate_limit_backend: str = "memory"
    rate_limit_default_per_minute: int = 120
    rate_limit_auth_per_minute: int = 10
    rate_limit_ai_per_minute: int = 20
    rate_limit_heavy_per_minute: int = 30
    # Durable analysis-job worker (#93). ``analysis_worker_autostart`` gates the
    # background daemon thread started in ``app.main``'s lifespan; tests set it
    # False so they drive ``AnalysisWorker.run_once()`` deterministically instead
    # of racing a real thread. The poll interval bounds how long the loop sleeps
    # between empty polls; the lease bounds how long a claimed job is owned before
    # a future stale-job sweep may reclaim it.
    analysis_worker_autostart: bool = True
    analysis_job_poll_interval_seconds: int = 5
    analysis_job_lease_seconds: int = 300
    clone_timeout_seconds: int = 120
    max_upload_size_bytes: int = 100 * 1024 * 1024
    max_clone_size_bytes: int = 500 * 1024 * 1024
    # Bound decompressed archive size / member count during extraction
    # (app/storage/local.py) and total repository-wide file count after
    # parsing (app/services/repository_service.py) — the compressed upload
    # and post-hoc clone size are already capped above, but nothing bounded
    # the decompressed/extracted side, a zip/tar-bomb and hostile-input gap.
    max_extracted_size_bytes: int = 1024 * 1024 * 1024  # 1 GiB decompressed cap
    max_extracted_entries: int = 50_000  # archive member count cap
    max_file_count: int = 50_000  # repository-wide file count cap
    # AI-provider egress is fail-safe by default.  Local/internal endpoints are
    # never enabled implicitly; deployments that need one must opt in with an
    # exact administrator-owned URL and CIDR in self_hosted mode.
    ai_egress_mode: str = "hosted"
    ai_egress_allowed_base_urls: Annotated[list[str], NoDecode] = Field(default_factory=list)
    ai_egress_allowed_cidrs: Annotated[list[str], NoDecode] = Field(default_factory=list)

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

    @field_validator("ai_egress_allowed_base_urls", "ai_egress_allowed_cidrs", mode="before")
    @classmethod
    def parse_egress_lists(cls, value: str | list[str] | None) -> list[str]:
        if value is None:
            return []
        if isinstance(value, str):
            return [entry.strip() for entry in value.split(",") if entry.strip()]
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

    @field_validator("rate_limit_backend")
    @classmethod
    def validate_rate_limit_backend(cls, value: str) -> str:
        normalized = value.lower()
        if normalized not in {"memory", "redis"}:
            raise ValueError(f"Unsupported rate-limit backend: {value}")
        return normalized

    @field_validator("ai_egress_mode")
    @classmethod
    def validate_ai_egress_mode(cls, value: str) -> str:
        normalized = value.lower()
        if normalized not in {"hosted", "self_hosted"}:
            raise ValueError("AI_EGRESS_MODE must be either 'hosted' or 'self_hosted'.")
        return normalized

    @field_validator("ai_egress_allowed_base_urls")
    @classmethod
    def validate_ai_egress_allowed_base_urls(cls, value: list[str]) -> list[str]:
        normalized: list[str] = []
        for entry in value:
            try:
                normalized.append(normalize_base_url(entry).base_url)
            except DestinationPolicyError as exc:
                raise ValueError("AI_EGRESS_ALLOWED_BASE_URLS contains an invalid URL.") from exc
        return normalized

    @field_validator("ai_egress_allowed_cidrs")
    @classmethod
    def validate_ai_egress_allowed_cidrs(cls, value: list[str]) -> list[str]:
        normalized: list[str] = []
        for entry in value:
            try:
                normalized.append(str(ipaddress.ip_network(entry, strict=True)))
            except (TypeError, ValueError) as exc:
                raise ValueError("AI_EGRESS_ALLOWED_CIDRS contains an invalid CIDR.") from exc
        return normalized

    @field_validator(
        "analysis_job_poll_interval_seconds",
        "analysis_job_lease_seconds",
        "clone_timeout_seconds",
        "max_upload_size_bytes",
        "max_clone_size_bytes",
        "max_extracted_size_bytes",
        "max_extracted_entries",
        "max_file_count",
        "access_token_ttl_seconds",
        "refresh_token_ttl_seconds",
        "rate_limit_default_per_minute",
        "rate_limit_auth_per_minute",
        "rate_limit_ai_per_minute",
        "rate_limit_heavy_per_minute",
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
    def resolve_ai_encryption_key(self) -> "Settings":
        lenient = self.app_env in {"development", "test"}
        if not self.ai_encryption_key:
            if not lenient:
                raise ValueError("AI_ENCRYPTION_KEY must be set outside development/test environments.")
            self.ai_encryption_key = _DEV_AI_ENCRYPTION_KEY
            return self
        try:
            decoded = base64.urlsafe_b64decode(self.ai_encryption_key.encode("utf-8"))
        except (binascii.Error, ValueError) as exc:
            raise ValueError("AI_ENCRYPTION_KEY must be a URL-safe base64-encoded 32-byte Fernet key.") from exc
        if len(decoded) != FERNET_KEY_BYTES:
            raise ValueError(
                f"AI_ENCRYPTION_KEY must decode to exactly {FERNET_KEY_BYTES} bytes (a Fernet key)."
            )
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
