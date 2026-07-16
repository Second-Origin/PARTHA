from datetime import UTC, datetime
from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import MetaData, Table, create_engine, func, inspect, select

BACKEND_ROOT = Path(__file__).resolve().parents[1]


def test_migrations_upgrade_and_downgrade_run_clean(tmp_path, monkeypatch):
    """The full revision chain applies and reverses on a fresh database.

    Alembic's env.py reads the URL from settings, so point it at a throwaway
    SQLite file. Running up -> down -> up proves both directions and that the
    down does not leave state that blocks a re-apply.
    """
    database_path = tmp_path / "migration-roundtrip.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{database_path}")
    monkeypatch.setenv("CORS_ORIGINS", "http://testserver")

    from app.core import config

    config.get_settings.cache_clear()
    try:
        cfg = Config(str(BACKEND_ROOT / "alembic.ini"))
        cfg.set_main_option("script_location", str(BACKEND_ROOT / "alembic"))

        command.upgrade(cfg, "head")
        command.downgrade(cfg, "base")
        command.upgrade(cfg, "head")
    finally:
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
