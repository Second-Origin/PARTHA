from pathlib import Path

from alembic import command
from alembic.config import Config

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
