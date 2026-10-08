from pathlib import Path
import os

import pytest

from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

from sqlalchemy import create_engine, delete, select
from sqlalchemy.orm import sessionmaker

from app.auth.service import AuthService
from app.core.config import Settings
from app.core.exceptions import ValidationServiceError
from app.models.base import Base
from app.models.installation_bootstrap import InstallationBootstrap
from app.models.user import User


def test_last_user_deletion_does_not_reopen_bootstrap(client):
    from app.core.database import SessionLocal

    assert (
        client.post(
            "/auth/register", json={"email": "first@example.com", "password": "correct-horse-battery-staple"}
        ).status_code
        == 201
    )
    with SessionLocal() as db:
        db.execute(delete(User))
        db.commit()
        assert db.scalars(select(InstallationBootstrap)).one() is not None
    response = client.post(
        "/auth/register", json={"email": "later@example.com", "password": "correct-horse-battery-staple"}
    )
    assert response.status_code == 422


@pytest.mark.parametrize("backend", ["sqlite", "postgresql"])
def test_concurrent_distinct_bootstrap_claims(tmp_path, backend):
    if backend == "postgresql" and not os.environ.get("PARTHA_TEST_PG_URL"):
        pytest.skip("PostgreSQL disposable test database unavailable")
    pg_url = None
    if backend == "postgresql":
        from tests.test_approved_emails_migration import _database_url

        pg_url = _database_url(tmp_path)
    engine = create_engine(
        pg_url or f"sqlite:///{tmp_path / 'race.db'}",
        connect_args={} if pg_url else {"check_same_thread": False, "timeout": 20},
    )
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine)
    barrier = Barrier(2)
    settings = Settings(app_env="test")

    def register(index):
        with factory() as db:
            barrier.wait(timeout=10)
            try:
                AuthService(db, settings).register(f"user{index}@example.com", "correct-horse-battery-staple")
                return "created"
            except ValidationServiceError:
                return "rejected"

    with ThreadPoolExecutor(max_workers=2) as pool:
        assert sorted(pool.map(register, [1, 2])) == ["created", "rejected"]
    with factory() as db:
        assert len(db.scalars(select(User)).all()) == 1
        assert len(db.scalars(select(InstallationBootstrap)).all()) == 1
    engine.dispose()
    if pg_url:
        from tests.test_approved_emails_migration import _drop_pg_database

        _drop_pg_database(pg_url)


def test_failed_registration_claim_rolls_back(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'rollback.db'}")
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine)
    with factory() as db:
        service = AuthService(db, Settings(app_env="test"))
        assert service._claim_installation()
        db.rollback()
        assert service._claim_installation()
        db.rollback()
    engine.dispose()


def test_migration_preserves_used_approval_after_account_deletion(tmp_path, monkeypatch):
    from alembic import command
    from alembic.config import Config
    from sqlalchemy import text

    url = f"sqlite:///{tmp_path / 'upgrade.db'}"
    monkeypatch.setenv("DATABASE_URL", url)
    from app.core.config import get_settings

    get_settings.cache_clear()
    cfg = Config(str(Path(__file__).parents[1] / "alembic.ini"))
    cfg.set_main_option("script_location", str(Path(__file__).parents[1] / "alembic"))
    command.upgrade(cfg, "0018_conversation_msg_indexes")
    engine = create_engine(url)
    with engine.begin() as connection:
        connection.execute(
            text(
                "INSERT INTO approved_emails (id,email,created_at,used_at,added_by) VALUES ('prior','prior@example.com',CURRENT_TIMESTAMP,CURRENT_TIMESTAMP,'first-user-bootstrap')"
            )
        )
    command.upgrade(cfg, "head")
    with engine.connect() as connection:
        assert connection.execute(text("SELECT id FROM installation_bootstrap")).scalar() == "installation"
    with pytest.raises(RuntimeError, match="Cannot remove a claimed"):
        command.downgrade(cfg, "0018_conversation_msg_indexes")
    engine.dispose()
    get_settings.cache_clear()
