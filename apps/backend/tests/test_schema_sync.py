from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect

from app.core.schema_sync import (
    SchemaDriftError,
    current_revision,
    ensure_schema_in_sync,
    head_revision,
    stamp_head,
)

BACKEND_ROOT = Path(__file__).resolve().parents[1]


def _alembic_cfg() -> Config:
    cfg = Config(str(BACKEND_ROOT / "alembic.ini"))
    cfg.set_main_option("script_location", str(BACKEND_ROOT / "alembic"))
    return cfg


@pytest.fixture()
def db_url(tmp_path, monkeypatch):
    """Point global settings at a throwaway SQLite file.

    ``ensure_schema_in_sync``'s auto-upgrade path calls
    ``alembic.command.upgrade``, which reads the database URL from process
    settings (``alembic/env.py``) rather than the ``Engine`` object passed
    to it, so the two must agree for these tests to target the same file.
    """

    database_path = tmp_path / "schema-sync-test.db"
    url = f"sqlite:///{database_path}"
    monkeypatch.setenv("DATABASE_URL", url)
    monkeypatch.setenv("CORS_ORIGINS", "http://testserver")

    from app.core import config

    config.get_settings.cache_clear()
    yield url
    config.get_settings.cache_clear()


def test_fresh_database_via_create_all_gets_stamped_at_head(db_url):
    from app.models.base import Base

    engine = create_engine(db_url)
    try:
        assert inspect(engine).get_table_names() == []
        Base.metadata.create_all(bind=engine)
        stamp_head(engine)
        assert current_revision(engine) == head_revision()
    finally:
        engine.dispose()


def test_behind_head_database_auto_upgrades_when_no_physical_conflict(db_url):
    """A cleanly-stamped, genuinely-behind database upgrades without incident.

    0007 only drops a column -- there is no table it could collide with, so
    this is exactly the case that should auto-upgrade rather than refuse.
    """

    engine = create_engine(db_url)
    try:
        command.upgrade(_alembic_cfg(), "0006_analysis_jobs")
        assert current_revision(engine) == "0006_analysis_jobs"

        ensure_schema_in_sync(engine, app_env="development")

        assert current_revision(engine) == head_revision()
        columns = {column["name"] for column in inspect(engine).get_columns("repositories")}
        assert "data_source" not in columns
    finally:
        engine.dispose()


def test_physical_drift_refuses_with_actionable_recovery_instead_of_crashing(db_url):
    """The create_all-without-stamp state must never attempt a blind upgrade.

    Simulates the reported bug: stamped at 0005, but 0006's table already
    exists physically, as if an earlier ``create_all`` built it without ever
    advancing the stamp. A blind ``alembic upgrade head`` would crash with
    "table analysis_jobs already exists"; this must instead raise a clear,
    actionable error and leave the stamp untouched -- no crash loop.
    """

    from app.models.analysis_job import AnalysisJob

    engine = create_engine(db_url)
    try:
        command.upgrade(_alembic_cfg(), "0005_revision_snapshots")
        AnalysisJob.__table__.create(bind=engine)

        with pytest.raises(SchemaDriftError) as excinfo:
            ensure_schema_in_sync(engine, app_env="development")

        message = str(excinfo.value)
        assert "analysis_jobs" in message
        assert "0006_analysis_jobs" in message
        assert "alembic stamp 0006_analysis_jobs" in message
        assert "alembic upgrade head" in message
        # Refusing must not leave the database half-upgraded or looping.
        assert current_revision(engine) == "0005_revision_snapshots"
    finally:
        engine.dispose()


def test_physical_drift_does_not_silently_skip_a_pending_column_migration(db_url):
    """The recommended stamp target must never jump past an unverified migration.

    0007 (a plain column drop) gives no physical evidence of having already
    run, so the recovery recommendation must stop at 0006 -- not 0007 --
    even though 0007 is technically 'pending' too. Recommending a stamp at
    0007 would silently skip the real, still-needed column drop forever.
    """

    from app.models.analysis_job import AnalysisJob

    engine = create_engine(db_url)
    try:
        command.upgrade(_alembic_cfg(), "0005_revision_snapshots")
        AnalysisJob.__table__.create(bind=engine)

        with pytest.raises(SchemaDriftError) as excinfo:
            ensure_schema_in_sync(engine, app_env="development")

        assert "alembic stamp 0006_analysis_jobs" in str(excinfo.value)
        assert "0007" not in str(excinfo.value).split("Recover with:")[1].split("\n")[1]
    finally:
        engine.dispose()


@pytest.mark.parametrize("app_env", ["production", "staging"])
def test_production_and_staging_never_auto_migrate(db_url, app_env):
    engine = create_engine(db_url)
    try:
        command.upgrade(_alembic_cfg(), "0006_analysis_jobs")

        ensure_schema_in_sync(engine, app_env=app_env)

        assert current_revision(engine) == "0006_analysis_jobs"
    finally:
        engine.dispose()


def test_up_to_date_database_is_a_no_op(db_url):
    engine = create_engine(db_url)
    try:
        command.upgrade(_alembic_cfg(), "head")

        ensure_schema_in_sync(engine, app_env="development")

        assert current_revision(engine) == head_revision()
    finally:
        engine.dispose()
