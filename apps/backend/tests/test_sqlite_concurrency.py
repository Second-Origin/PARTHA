"""SQLite concurrency hardening (#162): WAL journaling and a busy-wait timeout.

Without WAL, SQLite's default rollback-journal mode briefly locks out
readers around each write commit; a writer committing rapidly (mirrors the
analysis worker persisting many facts stage by stage) alongside readers
polling concurrently (mirrors repeated status/list requests) adds up to real
"database is locked" errors -- exactly what #161's validation produced. WAL
lets a reader always see the last committed snapshot without waiting on the
writer at all. PostgreSQL is unaffected: it uses MVCC and never takes this
kind of lock for an ordinary transaction.
"""

import sqlite3
import threading
import time
from unittest.mock import MagicMock

from sqlalchemy import text

from app.core.database import SQLITE_BUSY_TIMEOUT_MS, _configure_sqlite_concurrency
from tests.conftest import register_user


def test_wal_and_busy_timeout_applied_on_a_real_sqlite_connection(tmp_path):
    connection = sqlite3.connect(str(tmp_path / "pragma-check.db"))
    try:
        _configure_sqlite_concurrency(connection, None)
        cursor = connection.cursor()
        assert cursor.execute("PRAGMA journal_mode").fetchone()[0].lower() == "wal"
        assert cursor.execute("PRAGMA busy_timeout").fetchone()[0] == SQLITE_BUSY_TIMEOUT_MS
    finally:
        connection.close()


def test_pragmas_are_never_attempted_on_a_non_sqlite_connection():
    not_sqlite = MagicMock()

    _configure_sqlite_concurrency(not_sqlite, None)

    not_sqlite.cursor.assert_not_called()


def test_concurrent_reads_survive_a_writer_committing_rapidly(client):
    """The reader/writer shape from #162's reproduction, deterministically.

    SQLite's default rollback-journal mode briefly locks out readers around
    each write commit (not only for genuinely long-held transactions) --
    with a writer committing continuously (mirrors the analysis worker
    persisting many nodes/observations/diagnostics stage by stage) and
    readers polling concurrently (mirrors repeated status/list requests),
    that adds up to real "database is locked" errors, reproduced below with
    the reader's own busy-wait removed so contention cannot hide behind a
    generous default retry. WAL removes the collision entirely: a WAL reader
    always sees the last committed snapshot without waiting on the writer at
    all, regardless of how often it commits.
    """

    from app.core.database import SessionLocal

    auth = register_user(client, "sqlite-concurrency@example.com")
    user_id = auth["user"]["id"]

    stop = threading.Event()
    errors: list[BaseException] = []
    reads_done = 0

    def commit_rapidly() -> None:
        session = SessionLocal()
        counter = 0
        try:
            while not stop.is_set():
                session.execute(
                    text("UPDATE users SET email = :email WHERE id = :id"),
                    {"email": f"concurrency-{counter}@example.com", "id": user_id},
                )
                session.commit()
                counter += 1
        except BaseException as exc:  # noqa: BLE001 - surfaced to the assertion below
            errors.append(exc)
        finally:
            session.rollback()
            session.close()

    def read_repeatedly() -> None:
        nonlocal reads_done
        session = SessionLocal()
        # Zero tolerance: fail immediately on any lock instead of masking
        # real contention behind the driver's own generous default retry.
        session.execute(text("PRAGMA busy_timeout=0"))
        try:
            while not stop.is_set():
                session.execute(text("SELECT * FROM users WHERE id = :id"), {"id": user_id}).fetchall()
                reads_done += 1
        except BaseException as exc:  # noqa: BLE001 - surfaced to the assertion below
            errors.append(exc)
        finally:
            session.close()

    writer = threading.Thread(target=commit_rapidly)
    readers = [threading.Thread(target=read_repeatedly) for _ in range(3)]
    writer.start()
    for reader in readers:
        reader.start()

    time.sleep(0.5)
    stop.set()
    writer.join(timeout=5)
    for reader in readers:
        reader.join(timeout=5)

    assert not writer.is_alive() and all(not reader.is_alive() for reader in readers), "a thread did not finish"
    assert reads_done > 0, "the read loop never completed a single read -- test is not exercising real contention"
    assert not errors, errors
