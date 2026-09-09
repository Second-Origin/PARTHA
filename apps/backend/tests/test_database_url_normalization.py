"""DATABASE_URL scheme normalization (#340).

Managed Postgres providers (Render among them) hand back a bare
postgres(ql):// connection string, but the only driver this project installs
is psycopg 3 -- create_engine on a bare postgresql:// URL raises
ModuleNotFoundError for psycopg2, which is never installed. Settings must
normalize the scheme so a provisioned connection string works unmodified.
"""

import pytest

from app.core.config import Settings


def _settings(database_url: str) -> Settings:
    return Settings(
        database_url=database_url,
        app_env="test",
        auth_secret_key="x" * 32,
        ai_encryption_key="",
    )


@pytest.mark.parametrize(
    "given,expected",
    [
        ("postgresql://user:pass@host:5432/db", "postgresql+psycopg://user:pass@host:5432/db"),
        ("postgres://user:pass@host:5432/db", "postgresql+psycopg://user:pass@host:5432/db"),
        ("postgresql+psycopg://user:pass@host:5432/db", "postgresql+psycopg://user:pass@host:5432/db"),
        ("sqlite:///./.local/partha.db", "sqlite:///./.local/partha.db"),
    ],
)
def test_database_url_normalizes_to_the_installed_driver(given: str, expected: str) -> None:
    assert _settings(given).database_url == expected


def test_normalized_url_actually_resolves_to_the_installed_psycopg_driver() -> None:
    from sqlalchemy import create_engine

    settings = _settings("postgresql://user:pass@host:5432/db")
    engine = create_engine(settings.database_url)

    assert engine.dialect.driver == "psycopg"


def test_unsupported_scheme_is_still_rejected() -> None:
    with pytest.raises(ValueError, match="Unsupported database URL scheme"):
        _settings("mysql://user:pass@host:3306/db")
