import os
from collections.abc import Generator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient


@pytest.fixture()
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Generator[TestClient, None, None]:
    database_path = tmp_path / "partha-test.db"
    storage_path = tmp_path / "storage"
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{database_path}")
    monkeypatch.setenv("STORAGE_PATH", str(storage_path))
    monkeypatch.setenv("AUTO_CREATE_TABLES", "true")
    monkeypatch.setenv("CORS_ORIGINS", "http://testserver")

    from app.core import config

    config.get_settings.cache_clear()

    import app.core.database as database

    settings = config.get_settings()
    database.settings = settings
    database.engine.dispose()
    database.connect_args = {"check_same_thread": False}
    database.engine = database.create_engine(settings.database_url, pool_pre_ping=True, connect_args=database.connect_args)
    database.SessionLocal.configure(bind=database.engine)

    from app.main import create_app
    from app.models.base import Base

    Base.metadata.create_all(bind=database.engine)
    with TestClient(create_app()) as test_client:
        yield test_client

    os.environ.pop("DATABASE_URL", None)
    os.environ.pop("STORAGE_PATH", None)
    os.environ.pop("AUTO_CREATE_TABLES", None)
    os.environ.pop("CORS_ORIGINS", None)
    config.get_settings.cache_clear()
