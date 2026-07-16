import sqlite3
from collections.abc import Generator
from pathlib import Path

from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import get_settings

settings = get_settings()


@event.listens_for(Engine, "connect")
def _enable_sqlite_foreign_keys(dbapi_connection, _connection_record) -> None:
    """Enforce foreign keys on SQLite (off by default in the driver).

    The Repository Intelligence snapshot tables (#88) depend on foreign-key and
    composite-key enforcement for same-snapshot integrity; SQLite ignores
    foreign keys unless ``PRAGMA foreign_keys=ON`` is set per connection. This
    is a no-op on PostgreSQL, which always enforces them. Registered on the
    ``Engine`` class so it also applies to engines rebuilt by the test fixtures.
    """

    if isinstance(dbapi_connection, sqlite3.Connection):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()


connect_args = {}
if settings.database_url.startswith("sqlite"):
    connect_args["check_same_thread"] = False
    database_path = settings.database_url.replace("sqlite:///", "")
    if database_path and database_path != ":memory:":
        Path(database_path).parent.mkdir(parents=True, exist_ok=True)

engine = create_engine(settings.database_url, pool_pre_ping=True, connect_args=connect_args)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
