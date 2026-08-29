"""Migration-level coverage for #374, revision 0016_approved_emails.

Runs against SQLite by default and against a real, disposable PostgreSQL
database when ``PARTHA_TEST_PG_URL`` is set -- the same fixture idiom as
test_repository_lineage_migration.py's ``lineage_migration_db``.
"""

import uuid
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect, select
from sqlalchemy.engine import make_url

BACKEND_ROOT = Path(__file__).resolve().parents[1]
PG_URL = __import__("os").environ.get("PARTHA_TEST_PG_URL")

SEEDED_EMAIL = "parthrohit60@gmail.com"


def _alembic_config() -> Config:
    cfg = Config(str(BACKEND_ROOT / "alembic.ini"))
    cfg.set_main_option("script_location", str(BACKEND_ROOT / "alembic"))
    return cfg


def _database_url(tmp_path) -> str:
    if not PG_URL:
        return f"sqlite:///{tmp_path / 'approved-emails-migration.db'}"
    admin_url = make_url(PG_URL)
    database_name = f"partha_approved_emails_migration_{uuid.uuid4().hex}"
    admin_engine = create_engine(admin_url, isolation_level="AUTOCOMMIT")
    try:
        with admin_engine.connect() as connection:
            connection.exec_driver_sql(f'CREATE DATABASE "{database_name}"')
    finally:
        admin_engine.dispose()
    return admin_url.set(database=database_name).render_as_string(hide_password=False)


def _drop_pg_database(database_url: str) -> None:
    if not PG_URL:
        return
    admin_url = make_url(PG_URL)
    target = make_url(database_url)
    admin_engine = create_engine(admin_url, isolation_level="AUTOCOMMIT")
    try:
        with admin_engine.connect() as connection:
            connection.exec_driver_sql(f'DROP DATABASE IF EXISTS "{target.database}" WITH (FORCE)')
    finally:
        admin_engine.dispose()


@pytest.fixture()
def approved_emails_migration_db(tmp_path, monkeypatch):
    database_url = _database_url(tmp_path)
    monkeypatch.setenv("DATABASE_URL", database_url)
    monkeypatch.setenv("CORS_ORIGINS", "http://testserver")
    from app.core import config

    config.get_settings.cache_clear()
    engine = create_engine(database_url)
    try:
        yield database_url, engine
    finally:
        engine.dispose()
        config.get_settings.cache_clear()
        _drop_pg_database(database_url)


def test_fresh_database_creates_approved_emails_with_the_expected_shape(approved_emails_migration_db):
    database_url, engine = approved_emails_migration_db
    command.upgrade(_alembic_config(), "head")

    inspector = inspect(engine)
    assert "approved_emails" in inspector.get_table_names()
    # invite_tokens is left in place as a historical audit record -- not
    # dropped by this migration.
    assert "invite_tokens" in inspector.get_table_names()

    columns = {column["name"] for column in inspector.get_columns("approved_emails")}
    assert columns == {"id", "email", "note", "added_by", "created_at", "used_at", "used_by_user_id"}

    unique_constraints = inspector.get_unique_constraints("approved_emails")
    assert any(set(uc["column_names"]) == {"email"} for uc in unique_constraints) or any(
        set(index["column_names"]) == {"email"} and index["unique"]
        for index in inspector.get_indexes("approved_emails")
    )


def test_the_product_owner_is_pre_approved_by_the_migration_itself(approved_emails_migration_db):
    database_url, engine = approved_emails_migration_db
    command.upgrade(_alembic_config(), "head")

    from sqlalchemy.orm import sessionmaker

    from app.models.approved_email import ApprovedEmail

    Session = sessionmaker(bind=engine)
    with Session() as session:
        seeded = session.scalars(select(ApprovedEmail).where(ApprovedEmail.email == SEEDED_EMAIL)).one()
        assert seeded.used_at is None
        assert seeded.used_by_user_id is None
        assert seeded.added_by == "migration:0016_approved_emails"
        assert seeded.note is not None and "product owner" in seeded.note.lower()


def test_downgrade_then_reupgrade_round_trips_cleanly_and_reseeds(approved_emails_migration_db):
    database_url, engine = approved_emails_migration_db
    cfg = _alembic_config()
    command.upgrade(cfg, "head")
    command.downgrade(cfg, "0015_oauth_identities")

    inspector = inspect(engine)
    assert "approved_emails" not in inspector.get_table_names()

    command.upgrade(cfg, "head")
    inspector = inspect(engine)
    assert "approved_emails" in inspector.get_table_names()

    from sqlalchemy.orm import sessionmaker

    from app.models.approved_email import ApprovedEmail

    Session = sessionmaker(bind=engine)
    with Session() as session:
        matches = session.scalars(select(ApprovedEmail).where(ApprovedEmail.email == SEEDED_EMAIL)).all()
        assert len(matches) == 1


def test_registration_actually_works_against_a_freshly_migrated_database(approved_emails_migration_db, monkeypatch):
    """End-to-end proof this migration's schema is what the live app
    actually uses, not just a shape check -- the seeded owner email can
    register through the real endpoint on a database built by nothing but
    Alembic (no AUTO_CREATE_TABLES)."""
    database_url, engine = approved_emails_migration_db
    monkeypatch.setenv("AUTO_CREATE_TABLES", "false")
    command.upgrade(_alembic_config(), "head")

    from app.core import config
    from app.core.schema_sync import stamp_head

    config.get_settings.cache_clear()
    import app.core.database as database

    settings = config.get_settings()
    database.settings = settings
    database.engine.dispose()
    database.engine = database.create_engine(settings.database_url, pool_pre_ping=True)
    database.SessionLocal.configure(bind=database.engine)
    stamp_head(database.engine)

    from fastapi.testclient import TestClient

    from app.main import create_app

    with TestClient(create_app()) as client:
        response = client.post(
            "/auth/register", json={"email": SEEDED_EMAIL, "password": "correct-horse-battery-staple"}
        )
        assert response.status_code == 201, response.text
        assert response.json()["user"]["email"] == SEEDED_EMAIL
