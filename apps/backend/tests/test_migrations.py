import os
import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import MetaData, Table, create_engine, func, inspect, select
from sqlalchemy.engine import make_url

BACKEND_ROOT = Path(__file__).resolve().parents[1]


@contextmanager
def _migration_database_url(tmp_path: Path) -> Iterator[str]:
    """Yield a clean migration target, preferring isolated PostgreSQL in CI."""
    postgres_url = os.environ.get("PARTHA_TEST_PG_URL")
    if not postgres_url:
        yield f"sqlite:///{tmp_path / 'migration-roundtrip.db'}"
        return

    admin_url = make_url(postgres_url)
    database_name = f"partha_migration_{uuid.uuid4().hex}"
    migration_url = admin_url.set(database=database_name).render_as_string(
        hide_password=False
    )
    admin_engine = create_engine(admin_url, isolation_level="AUTOCOMMIT")
    quoted_database_name = admin_engine.dialect.identifier_preparer.quote(database_name)
    database_created = False
    try:
        with admin_engine.connect() as connection:
            connection.exec_driver_sql(f"CREATE DATABASE {quoted_database_name}")
        database_created = True
        yield migration_url
    finally:
        try:
            if database_created:
                with admin_engine.connect() as connection:
                    connection.exec_driver_sql(
                        f"DROP DATABASE IF EXISTS {quoted_database_name} WITH (FORCE)"
                    )
        finally:
            admin_engine.dispose()


def test_migrations_upgrade_and_downgrade_run_clean(tmp_path, monkeypatch):
    """The full revision chain applies and reverses on a fresh database.

    CI uses an isolated PostgreSQL database. Local runs without PostgreSQL use
    a throwaway SQLite file. Running up -> down -> up proves both directions
    and that the downgrade does not leave state that blocks a re-apply.
    """
    with _migration_database_url(tmp_path) as database_url:
        monkeypatch.setenv("DATABASE_URL", database_url)
        monkeypatch.setenv("CORS_ORIGINS", "http://testserver")

        from app.core import config

        config.get_settings.cache_clear()
        probe_engine = create_engine(database_url)
        try:
            assert inspect(probe_engine).get_table_names() == []

            cfg = Config(str(BACKEND_ROOT / "alembic.ini"))
            cfg.set_main_option("script_location", str(BACKEND_ROOT / "alembic"))

            command.upgrade(cfg, "head")
            assert "repositories" in inspect(probe_engine).get_table_names()
            snapshot_index = next(
                index
                for index in inspect(probe_engine).get_indexes("analysis_jobs")
                if index["name"] == "uq_analysis_jobs_snapshot_id"
            )
            assert bool(snapshot_index["unique"])
            assert snapshot_index["column_names"] == ["snapshot_id"]
            effective_index = next(
                index
                for index in inspect(probe_engine).get_indexes("analysis_jobs")
                if index["name"] == "uq_analysis_jobs_effective_identity"
            )
            assert bool(effective_index["unique"])
            assert effective_index["column_names"] == [
                "repository_id",
                "revision_value",
                "config_hash",
            ]

            command.downgrade(cfg, "base")
            assert "repositories" not in inspect(probe_engine).get_table_names()

            command.upgrade(cfg, "head")
            assert "repositories" in inspect(probe_engine).get_table_names()
        finally:
            probe_engine.dispose()
            config.get_settings.cache_clear()


def test_migrations_accept_percent_encoded_database_urls_online_and_offline(tmp_path, monkeypatch):
    """Percent-encoded URLs work in both Alembic execution modes."""
    database_url = f"sqlite:///{tmp_path / 'migration-percent-%40.db'}"
    monkeypatch.setenv("DATABASE_URL", database_url)
    monkeypatch.setenv("CORS_ORIGINS", "http://testserver")

    from app.core import config

    config.get_settings.cache_clear()
    probe_engine = create_engine(database_url)
    try:
        cfg = Config(str(BACKEND_ROOT / "alembic.ini"))
        cfg.set_main_option("script_location", str(BACKEND_ROOT / "alembic"))

        command.upgrade(cfg, "head")
        assert "repositories" in inspect(probe_engine).get_table_names()

        command.downgrade(cfg, "base")
        assert "repositories" not in inspect(probe_engine).get_table_names()

        monkeypatch.setenv(
            "DATABASE_URL",
            "postgresql+psycopg://user:p%40ss@localhost:5432/somedb",
        )
        config.get_settings.cache_clear()
        offline_cfg = Config(str(BACKEND_ROOT / "alembic.ini"))
        offline_cfg.set_main_option("script_location", str(BACKEND_ROOT / "alembic"))

        # 0005 includes a data backfill that requires a live connection, so
        # offline SQL generation intentionally stops at the latest
        # schema-only revision.
        command.upgrade(offline_cfg, "0004_ai_provider_configs", sql=True)
        command.downgrade(offline_cfg, "0004_ai_provider_configs:base", sql=True)
    finally:
        probe_engine.dispose()
        config.get_settings.cache_clear()


def test_revision_backfill_classifies_exact_legacy_values_and_downgrade_preserves_metadata(
    tmp_path, monkeypatch
):
    database_path = tmp_path / "migration-backfill.db"
    database_url = f"sqlite:///{database_path}"
    monkeypatch.setenv("DATABASE_URL", database_url)
    monkeypatch.setenv("CORS_ORIGINS", "http://testserver")

    from app.core import config

    config.get_settings.cache_clear()
    cfg = Config(str(BACKEND_ROOT / "alembic.ini"))
    cfg.set_main_option("script_location", str(BACKEND_ROOT / "alembic"))
    engine = create_engine(database_url)
    try:
        command.upgrade(cfg, "0004_ai_provider_configs")
        metadata = MetaData()
        repositories = Table("repositories", metadata, autoload_with=engine)
        now = datetime.now(UTC)
        common = {
            "owner_id": "00000000-0000-0000-0000-000000000000",
            "description": None,
            "source_url": None,
            "local_path": "/legacy",
            "size": 0,
            "file_count": 0,
            "status": "completed",
            "data_source": "real",
            "analysis_stage": None,
            "analysis_progress": 100,
            "uploaded_at": now,
            "analysed_at": now,
            "error_message": None,
            "file_tree": [],
            "created_at": now,
            "updated_at": now,
        }
        rows = [
            {
                **common,
                "id": "10000000-0000-0000-0000-000000000001",
                "name": "git",
                "source": "github",
                "branch": "main",
                "repo_metadata": {"commitSha": "a" * 40, "intelligence": {"nodes": ["legacy"]}},
            },
            {
                **common,
                "id": "10000000-0000-0000-0000-000000000002",
                "name": "upload",
                "source": "upload",
                "branch": None,
                "repo_metadata": {"commitSha": "sha256:" + "b" * 64},
            },
            {
                **common,
                "id": "10000000-0000-0000-0000-000000000003",
                "name": "invalid",
                "source": "github",
                "branch": "main",
                "repo_metadata": {"commitSha": "NOT-A-VALID-REVISION"},
            },
            {
                **common,
                "id": "10000000-0000-0000-0000-000000000004",
                "name": "missing",
                "source": "github",
                "branch": None,
                "repo_metadata": {"intelligence": {"relationships": ["legacy"]}},
            },
        ]
        with engine.begin() as connection:
            connection.execute(repositories.insert(), rows)

        command.upgrade(cfg, "head")
        # data_source was removed in 0007 (#96): always-"real", never a computed value.
        assert "data_source" not in {column["name"] for column in inspect(engine).get_columns("repositories")}
        upgraded = MetaData()
        upgraded_repositories = Table("repositories", upgraded, autoload_with=engine)
        with engine.connect() as connection:
            values = {
                row.id: row
                for row in connection.execute(
                    select(
                        upgraded_repositories.c.id,
                        upgraded_repositories.c.revision_kind,
                        upgraded_repositories.c.revision_value,
                        upgraded_repositories.c.revision_ref,
                        upgraded_repositories.c.repo_metadata,
                    )
                )
            }
        git = values[rows[0]["id"]]
        assert (git.revision_kind, git.revision_value, git.revision_ref) == (
            "git",
            "a" * 40,
            "refs/heads/main",
        )
        upload = values[rows[1]["id"]]
        assert (upload.revision_kind, upload.revision_value, upload.revision_ref) == (
            "upload",
            "sha256:" + "b" * 64,
            None,
        )
        assert values[rows[2]["id"]].revision_kind is None
        assert values[rows[3]["id"]].revision_value is None
        assert git.repo_metadata["intelligence"] == {"nodes": ["legacy"]}
        assert "ri_snapshots" in inspect(engine).get_table_names()
        with engine.connect() as connection:
            snapshots = Table("ri_snapshots", MetaData(), autoload_with=engine)
            assert connection.scalar(select(func.count()).select_from(snapshots)) == 0

        command.downgrade(cfg, "0004_ai_provider_configs")
        assert "ri_snapshots" not in inspect(engine).get_table_names()
        assert "data_source" in {column["name"] for column in inspect(engine).get_columns("repositories")}
        assert "revision_value" not in {column["name"] for column in inspect(engine).get_columns("repositories")}
        restored = Table("repositories", MetaData(), autoload_with=engine)
        with engine.connect() as connection:
            metadata_after = connection.scalar(
                select(restored.c.repo_metadata).where(restored.c.id == rows[0]["id"])
            )
        assert metadata_after["commitSha"] == "a" * 40
        assert metadata_after["intelligence"] == {"nodes": ["legacy"]}
    finally:
        engine.dispose()
        config.get_settings.cache_clear()
