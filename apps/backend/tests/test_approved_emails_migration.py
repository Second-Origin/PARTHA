"""Migration-level coverage for #374 (0016_approved_emails) and #465
(0017_remove_seeded_approval).

Runs against SQLite by default and against a real, disposable PostgreSQL
database when ``PARTHA_TEST_PG_URL`` is set -- the same fixture idiom as
test_repository_lineage_migration.py's ``lineage_migration_db``.
"""

import uuid
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect
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
    # See tests/conftest.py's `client` fixture: "test", not the default
    # "development", so AuthService's dev-only allowlist bypass (#384) never
    # applies here either.
    monkeypatch.setenv("APP_ENV", "test")
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


def _count_approved_rows(engine, **where) -> int:
    from sqlalchemy import text

    clause = " AND ".join(f"{column} = :{column}" for column in where) or "1 = 1"
    with engine.connect() as connection:
        return connection.execute(text(f"SELECT count(*) FROM approved_emails WHERE {clause}"), where).scalar_one()


def test_a_fresh_database_has_no_pre_approved_address(approved_emails_migration_db):
    """#465: nobody is pre-approved on a fresh install. A public, hardcoded
    address that skips the allowlist is claimable by anyone, because
    registration has no email verification."""
    database_url, engine = approved_emails_migration_db
    command.upgrade(_alembic_config(), "head")

    assert _count_approved_rows(engine) == 0
    assert _count_approved_rows(engine, email=SEEDED_EMAIL) == 0


def test_downgrade_then_reupgrade_round_trips_cleanly_and_seeds_nothing(approved_emails_migration_db):
    database_url, engine = approved_emails_migration_db
    cfg = _alembic_config()
    command.upgrade(cfg, "head")
    # Through both revisions: 0017's downgrade is a deliberate no-op, and
    # 0016's must not look for a row it no longer creates.
    command.downgrade(cfg, "0015_oauth_identities")

    inspector = inspect(engine)
    assert "approved_emails" not in inspector.get_table_names()

    command.upgrade(cfg, "head")
    inspector = inspect(engine)
    assert "approved_emails" in inspector.get_table_names()
    assert _count_approved_rows(engine) == 0


def _insert_old_seed(engine, *, used: bool) -> None:
    """Recreate exactly what the original 0016 wrote, for a database that
    already migrated before #465."""
    from sqlalchemy import text

    with engine.begin() as connection:
        connection.execute(
            text(
                "INSERT INTO approved_emails (id, email, note, added_by, created_at, used_at) "
                "VALUES (:id, :email, :note, :added_by, CURRENT_TIMESTAMP, "
                + ("CURRENT_TIMESTAMP" if used else "NULL")
                + ")"
            ),
            {
                "id": "00000000-0000-0000-0000-000000000001",
                "email": SEEDED_EMAIL,
                "note": "Pre-approved: product owner, seeded by migration 0016 so this change can never lock him out.",
                "added_by": "migration:0016_approved_emails",
            },
        )


def test_an_already_migrated_database_loses_the_unused_seed(approved_emails_migration_db):
    database_url, engine = approved_emails_migration_db
    cfg = _alembic_config()
    command.upgrade(cfg, "0016_approved_emails")
    _insert_old_seed(engine, used=False)
    assert _count_approved_rows(engine, email=SEEDED_EMAIL) == 1

    command.upgrade(cfg, "head")

    assert _count_approved_rows(engine, email=SEEDED_EMAIL) == 0


def test_a_seed_row_that_already_registered_an_account_is_left_alone(approved_emails_migration_db):
    """A migration can't tell that account's owner from anyone else, so it
    must not touch a row that was consumed."""
    database_url, engine = approved_emails_migration_db
    cfg = _alembic_config()
    command.upgrade(cfg, "0016_approved_emails")
    _insert_old_seed(engine, used=True)

    command.upgrade(cfg, "head")

    assert _count_approved_rows(engine, email=SEEDED_EMAIL) == 1


def test_a_row_an_operator_added_for_the_same_address_is_not_removed(approved_emails_migration_db):
    """Only the untouched seed goes: an operator who deliberately approved
    that address themselves (different id and marker) keeps their row."""
    database_url, engine = approved_emails_migration_db
    cfg = _alembic_config()
    command.upgrade(cfg, "0016_approved_emails")

    from sqlalchemy import text

    with engine.begin() as connection:
        connection.execute(
            text(
                "INSERT INTO approved_emails (id, email, added_by, created_at) "
                "VALUES (:id, :email, 'operator', CURRENT_TIMESTAMP)"
            ),
            {"id": str(uuid.uuid4()), "email": SEEDED_EMAIL},
        )

    command.upgrade(cfg, "head")

    assert _count_approved_rows(engine, email=SEEDED_EMAIL) == 1


def test_registration_actually_works_against_a_freshly_migrated_database(approved_emails_migration_db, monkeypatch):
    """End-to-end proof this migration's schema is what the live app
    actually uses, not just a shape check -- the first registrant becomes
    the owner through the real endpoint on a database built by nothing but
    Alembic (no AUTO_CREATE_TABLES), and the address that used to be
    seeded gets no special treatment afterwards (#465)."""
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
        first = client.post(
            "/auth/register", json={"email": "first-owner@example.com", "password": "correct-horse-battery-staple"}
        )
        assert first.status_code == 201, first.text
        assert first.json()["user"]["email"] == "first-owner@example.com"

        # An instance that already has an owner: the formerly-seeded address
        # is just another unapproved address, refused like any other.
        seeded = client.post("/auth/register", json={"email": SEEDED_EMAIL, "password": "correct-horse-battery-staple"})
        assert seeded.status_code == 422, seeded.text
        assert "hasn't been approved" in seeded.json()["message"]
