import sqlite3
from collections.abc import Generator
from pathlib import Path

from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import get_settings

settings = get_settings()


def _enable_sqlite_foreign_keys(dbapi_connection, _connection_record) -> None:
    """Enforce foreign keys on SQLite (off by default in the driver).

    The Repository Intelligence snapshot tables (#88) depend on foreign-key and
    composite-key enforcement for same-snapshot integrity; SQLite ignores
    foreign keys unless ``PRAGMA foreign_keys=ON`` is set per connection. This
    is a no-op on PostgreSQL, which always enforces them.
    """

    if isinstance(dbapi_connection, sqlite3.Connection):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()


def register_sqlite_foreign_key_enforcement() -> None:
    """Register SQLite foreign-key enforcement on every ``Engine`` connection.

    Registered on the ``Engine`` class so it also applies to engines the test
    fixtures build themselves. Idempotent, so tests can call it explicitly
    instead of importing this module for its side effect; production keeps the
    import-time registration below.
    """

    if not event.contains(Engine, "connect", _enable_sqlite_foreign_keys):
        event.listen(Engine, "connect", _enable_sqlite_foreign_keys)


register_sqlite_foreign_key_enforcement()

# A busy connection waits this long for a lock before raising "database is
# locked" (#162). 5s comfortably covers the worker's per-stage extraction
# work for an ordinary repository without masking a genuinely stuck writer
# behind a long, silent hang.
SQLITE_BUSY_TIMEOUT_MS = 5000


def _configure_sqlite_concurrency(dbapi_connection, _connection_record) -> None:
    """Enable WAL journaling and a busy-wait timeout on SQLite (#162).

    Development runs a background analysis-worker thread and the API's own
    request handlers against the same SQLite file. SQLite's default
    rollback-journal mode does not lock readers out for a transaction's
    whole open-but-uncommitted duration -- it briefly locks them out
    *around each individual commit*. The analysis worker persists many
    facts (nodes, observations, diagnostics) via frequent small commits
    during extraction, so with request handlers polling concurrently, those
    brief windows collide often enough to surface as real "database is
    locked" errors (confirmed empirically: reproducible in the thousands
    under sustained concurrent commit/read pressure). WAL mode removes this
    because a reader always sees the last committed snapshot independent of
    what the writer is currently doing, so it never has to wait on a commit
    at all. The busy timeout bounds the writer-vs-writer wait WAL still
    serializes (the worker's own heartbeat, a future second worker) instead
    of failing immediately. A no-op on PostgreSQL, which uses MVCC and never
    takes this kind of lock for an ordinary transaction.
    """

    if isinstance(dbapi_connection, sqlite3.Connection):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.fetchone()
        cursor.execute(f"PRAGMA busy_timeout={SQLITE_BUSY_TIMEOUT_MS}")
        cursor.close()


def register_sqlite_concurrency_settings() -> None:
    """Register WAL + busy-timeout on every ``Engine`` connection.

    Same registration pattern as ``register_sqlite_foreign_key_enforcement``:
    registered on the ``Engine`` class so it also applies to engines the test
    fixtures build themselves, and is idempotent.
    """

    if not event.contains(Engine, "connect", _configure_sqlite_concurrency):
        event.listen(Engine, "connect", _configure_sqlite_concurrency)


register_sqlite_concurrency_settings()

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
