"""Rehearse a full PARTHA backup and restore on disposable targets.

Proves the two things a production incident actually needs proven (#323):
that a backup of the *database* and the *repository storage directory* can
be taken, restored into a clean environment, and come back byte-for-byte
and row-for-row identical -- ownership, hashes, and the sealed ri.v1
snapshot's canonical graph hash included.

Like ``rehearse_migrations.py``, this command accepts no database URL and
cannot be pointed at an existing application database or storage directory:
every target it touches is one it created itself, named with a random
suffix, and removed again before exit (even on failure). SQLite is the
default and always available (backup is a file copy, matching how SQLite
itself defines a consistent backup); PostgreSQL is opt-in and reuses the
exact same disposable-server confirmation gate as the migration rehearsal
(``PARTHA_MIGRATION_REHEARSAL_CONFIRM=disposable`` and
``PARTHA_MIGRATION_REHEARSAL_PG_URL``), and additionally requires the
``pg_dump``/``pg_restore`` client binaries, which are not universally
present (see the module docstring's "Known gaps" note below and the
companion doc, docs/operations/backup-restore.md).

Known gaps this rehearsal does NOT prove, recorded here rather than implied:

- Encryption at rest and backup retention windows are the hosting
  provider's responsibility (Render-managed PostgreSQL), not this
  application's code, so they cannot be rehearsed by a local script --
  docs/operations/backup-restore.md records the expected policy instead.
- This rehearses a clean, quiescent restore. It does not rehearse restoring
  under concurrent production write load, nor point-in-time recovery to a
  timestamp between backups.
- Filesystem "backup" here is a directory copy, matching the local storage
  backend used in this rehearsal. A different storage backend (e.g. object
  storage) would need its own rehearsal, not this one.
"""

from __future__ import annotations

import argparse
import hashlib
import os
import shutil
import subprocess
import sys
import tempfile
import time
import uuid
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy import MetaData, Table, create_engine, inspect, select
from sqlalchemy.engine import URL, Engine, make_url
from sqlalchemy.exc import SQLAlchemyError

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

OWNER_ID = "10000000-0000-0000-0000-000000000323"
REPOSITORY_ID = "20000000-0000-0000-0000-000000000323"
SNAPSHOT_TABLES = ("users", "repositories", "ri_snapshots", "ri_nodes")


class RehearsalError(RuntimeError):
    """A safe-to-print rehearsal failure."""


def _alembic_config(database_url: str):
    from alembic.config import Config

    os.environ["DATABASE_URL"] = database_url
    os.environ.setdefault("CORS_ORIGINS", "http://backup-rehearsal.invalid")
    from app.core import config as app_config

    app_config.get_settings.cache_clear()
    cfg = Config(str(BACKEND_ROOT / "alembic.ini"))
    cfg.set_main_option("script_location", str(BACKEND_ROOT / "alembic"))
    return cfg


def _seed(database_url: str, storage_root: Path) -> dict[str, object]:
    """Bring a disposable database to head and seed representative,
    non-partner, non-private data: one user, one owner-scoped repository,
    and one sealed ri.v1 snapshot with a real evidence-backed node -- plus
    matching content on disk under ``storage_root``, the same pairing a real
    repository import produces."""

    from alembic import command

    # Deliberately NOT `from app.core.database import SessionLocal`: that
    # module binds its engine to get_settings().database_url once, at first
    # import, as process-wide module state -- a later os.environ change or
    # get_settings.cache_clear() (see _alembic_config below) cannot rebind
    # it. Using it here would silently target whatever database URL was
    # active the first time ANYTHING imported app.core.database in this
    # process (e.g. a real local Postgres from .env), not the disposable
    # target this function was given. Every session below is bound to an
    # engine this function creates itself, for exactly `database_url`.
    from app.auth.security import hash_password
    from app.intelligence.snapshot_store import Evidence, Revision, SnapshotStore
    from app.models.repository import RepositoryRecord
    from app.models.user import User
    from sqlalchemy.orm import Session

    cfg = _alembic_config(database_url)
    target_engine = create_engine(database_url)
    if inspect(target_engine).get_table_names():
        target_engine.dispose()
        raise RehearsalError("A rehearsal target was unexpectedly non-empty; refusing to continue.")
    target_engine.dispose()
    command.upgrade(cfg, "head")

    repo_dir = storage_root / "repositories" / REPOSITORY_ID
    repo_dir.mkdir(parents=True)
    readme = repo_dir / "README.md"
    readme.write_text("# backup-restore rehearsal fixture\n", encoding="utf-8")

    seed_engine = create_engine(database_url)
    session = Session(bind=seed_engine)
    try:
        # Committed separately, in FK order: there's no ORM relationship()
        # between User and RepositoryRecord for SQLAlchemy's unit-of-work to
        # infer insert order from, so a single flush can (and on real
        # Postgres, did, while SQLite's default FK enforcement stayed silent
        # about it) emit the repositories insert before the users insert.
        session.add(
            User(
                id=OWNER_ID,
                email="backup-rehearsal@example.invalid",
                password_hash=hash_password("not-a-real-password-rehearsal-only"),
                created_at=datetime.now(UTC),
            )
        )
        session.commit()
        session.add(
            RepositoryRecord(
                id=REPOSITORY_ID,
                owner_id=OWNER_ID,
                name="backup-restore-rehearsal",
                source="upload",
                local_path=str(repo_dir),
                status="completed",
                revision_kind="upload",
                revision_value=f"sha256:{'0' * 64}",
                file_count=1,
                size=readme.stat().st_size,
            )
        )
        session.commit()

        store = SnapshotStore(session)
        snapshot = store.begin(
            repository_id=REPOSITORY_ID,
            revision=Revision("upload", f"sha256:{'0' * 64}", None),
            schema_version="ri.v1",
            producer_version_set=["repository-inventory@1.1.0"],
        )
        store.add_node(
            snapshot,
            node_kind="repository",
            stable_key="repo:root",
            name="backup-restore-rehearsal",
            language=None,
            evidence=[
                Evidence(
                    path="README.md",
                    start_line=1,
                    end_line=1,
                    logical_line_count=1,
                    extractor="repository-inventory",
                    extractor_version="1.1.0",
                )
            ],
        )
        store.seal(snapshot)
        canonical_graph_hash = snapshot.canonical_graph_hash
    finally:
        session.close()
        seed_engine.dispose()

    return {
        "canonical_graph_hash": canonical_graph_hash,
        "readme_sha256": hashlib.sha256(readme.read_bytes()).hexdigest(),
    }


def _verify(database_url: str, storage_root: Path, expected: dict[str, object]) -> None:
    """Read the restored target back and assert it matches the seed exactly."""

    engine = create_engine(database_url)
    try:
        actual_tables = set(inspect(engine).get_table_names())
        missing = set(SNAPSHOT_TABLES) - actual_tables
        if missing:
            raise RehearsalError(f"Restored database is missing table(s): {', '.join(sorted(missing))}.")

        users = Table("users", MetaData(), autoload_with=engine)
        repositories = Table("repositories", MetaData(), autoload_with=engine)
        snapshots = Table("ri_snapshots", MetaData(), autoload_with=engine)

        with engine.connect() as connection:
            # Every schema also carries the migration-seeded system user
            # (app.models.user.SEED_USER_ID), so the total count is 2, not 1;
            # check for the specific rehearsal user by id instead.
            user_row = connection.execute(select(users.c.id).where(users.c.id == OWNER_ID)).one_or_none()
            if user_row is None:
                raise RehearsalError("The seeded rehearsal user did not survive restore.")

            repo_row = connection.execute(
                select(repositories.c.owner_id, repositories.c.local_path).where(repositories.c.id == REPOSITORY_ID)
            ).one_or_none()
            if repo_row is None:
                raise RehearsalError("The seeded repository row did not survive restore.")
            if repo_row.owner_id != OWNER_ID:
                raise RehearsalError("Restored repository lost its owner scoping.")

            snapshot_row = connection.execute(
                select(snapshots.c.canonical_graph_hash).where(snapshots.c.repository_id == REPOSITORY_ID)
            ).one_or_none()
            if snapshot_row is None:
                raise RehearsalError("The sealed snapshot did not survive restore.")
            if snapshot_row.canonical_graph_hash != expected["canonical_graph_hash"]:
                raise RehearsalError(
                    "Restored snapshot's canonical_graph_hash does not match the pre-backup value -- "
                    "the sealed graph identity did not survive restore intact."
                )
    finally:
        engine.dispose()

    restored_readme = storage_root / "repositories" / REPOSITORY_ID / "README.md"
    if not restored_readme.is_file():
        raise RehearsalError("Restored repository storage is missing README.md.")
    actual_hash = hashlib.sha256(restored_readme.read_bytes()).hexdigest()
    if actual_hash != expected["readme_sha256"]:
        raise RehearsalError("Restored repository file content hash does not match the pre-backup value.")


# --- SQLite: backup is a file copy, restore is a file copy -----------------


def _sqlite_backup_restore(_database_url_unused: str) -> None:
    with tempfile.TemporaryDirectory(prefix="partha-backup-rehearsal-") as workdir:
        root = Path(workdir)
        primary_db = root / "primary.db"
        primary_storage = root / "primary-storage"
        primary_storage.mkdir()

        started = time.monotonic()
        expected = _seed(f"sqlite:///{primary_db.as_posix()}", primary_storage)
        seed_seconds = time.monotonic() - started

        # "Backup": copy the consistent SQLite file and the storage tree.
        # "Restore": copy them again into a clean target -- proving the
        # backup artifact alone is sufficient, independent of the primary.
        backup_db = root / "backup.db"
        backup_storage = root / "backup-storage"
        shutil.copy2(primary_db, backup_db)
        shutil.copytree(primary_storage, backup_storage)

        restored_db = root / "restored.db"
        restored_storage = root / "restored-storage"
        restore_started = time.monotonic()
        shutil.copy2(backup_db, restored_db)
        shutil.copytree(backup_storage, restored_storage)
        restore_seconds = time.monotonic() - restore_started

        _verify(f"sqlite:///{restored_db.as_posix()}", restored_storage, expected)
        print(
            f"    seed: {seed_seconds:.2f}s, restore: {restore_seconds:.2f}s "
            "(local file copy -- not representative of production network/disk throughput)"
        )


# --- PostgreSQL: opt-in, mirrors rehearse_migrations.py's disposable-server gate ---


def _require_pg_tools() -> None:
    missing = [tool for tool in ("pg_dump", "pg_restore") if shutil.which(tool) is None]
    if missing:
        raise RehearsalError(
            f"PostgreSQL rehearsal requires {' and '.join(missing)} on PATH "
            "(the client tools, not just a Postgres driver)."
        )


def _postgres_rehearsal_admin_url() -> URL:
    if os.environ.get("PARTHA_MIGRATION_REHEARSAL_CONFIRM") != "disposable":
        raise RehearsalError(
            "PostgreSQL rehearsal requires PARTHA_MIGRATION_REHEARSAL_CONFIRM=disposable. "
            "Use only a dedicated rehearsal server."
        )
    configured_url = os.environ.get("PARTHA_MIGRATION_REHEARSAL_PG_URL")
    if not configured_url:
        raise RehearsalError(
            "PostgreSQL rehearsal requires PARTHA_MIGRATION_REHEARSAL_PG_URL; its value is never printed."
        )
    admin_url = make_url(configured_url)
    if admin_url.get_backend_name() != "postgresql":
        raise RehearsalError("PARTHA_MIGRATION_REHEARSAL_PG_URL must be a PostgreSQL URL.")
    return admin_url


@contextmanager
def _postgres_database(admin_url: URL, engine: Engine, name: str) -> Iterator[str]:
    quoted_name = engine.dialect.identifier_preparer.quote(name)
    with engine.connect() as connection:
        connection.exec_driver_sql(f"CREATE DATABASE {quoted_name}")
    try:
        yield admin_url.set(database=name).render_as_string(hide_password=False)
    finally:
        try:
            with engine.connect() as connection:
                connection.exec_driver_sql(f"DROP DATABASE IF EXISTS {quoted_name} WITH (FORCE)")
        except Exception:
            print(
                f"WARNING: failed to drop disposable rehearsal database {name}; it may require manual cleanup.",
                file=sys.stderr,
            )


def _postgres_backup_restore(_database_url_unused: str) -> None:
    _require_pg_tools()
    admin_url = _postgres_rehearsal_admin_url()
    engine = create_engine(admin_url, isolation_level="AUTOCOMMIT")
    suffix = uuid.uuid4().hex
    try:
        with tempfile.TemporaryDirectory(prefix="partha-backup-rehearsal-") as workdir:
            root = Path(workdir)
            primary_storage = root / "primary-storage"
            primary_storage.mkdir()
            dump_path = root / "backup.dump"

            with _postgres_database(admin_url, engine, f"partha_backup_rehearsal_primary_{suffix}") as primary_url:
                started = time.monotonic()
                expected = _seed(primary_url, primary_storage)
                seed_seconds = time.monotonic() - started

                primary_conn = make_url(primary_url)
                dump_env = {**os.environ, "PGPASSWORD": primary_conn.password or ""}
                subprocess.run(
                    [
                        "pg_dump",
                        "--format=custom",
                        f"--host={primary_conn.host}",
                        f"--port={primary_conn.port or 5432}",
                        f"--username={primary_conn.username}",
                        f"--dbname={primary_conn.database}",
                        f"--file={dump_path}",
                    ],
                    check=True,
                    env=dump_env,
                    capture_output=True,
                    text=True,
                )

            restored_storage = root / "restored-storage"
            shutil.copytree(primary_storage, restored_storage)

            with _postgres_database(admin_url, engine, f"partha_backup_rehearsal_restore_{suffix}") as restore_url:
                restore_conn = make_url(restore_url)
                restore_env = {**os.environ, "PGPASSWORD": restore_conn.password or ""}
                restore_started = time.monotonic()
                subprocess.run(
                    [
                        "pg_restore",
                        f"--host={restore_conn.host}",
                        f"--port={restore_conn.port or 5432}",
                        f"--username={restore_conn.username}",
                        f"--dbname={restore_conn.database}",
                        str(dump_path),
                    ],
                    check=True,
                    env=restore_env,
                    capture_output=True,
                    text=True,
                )
                restore_seconds = time.monotonic() - restore_started

                _verify(restore_url, restored_storage, expected)
                print(f"    seed: {seed_seconds:.2f}s, restore: {restore_seconds:.2f}s (pg_dump/pg_restore)")
    finally:
        engine.dispose()


def _run(name: str, operation: Callable[[str], None]) -> None:
    try:
        operation("")
    except RehearsalError:
        raise
    except subprocess.CalledProcessError as error:
        # pg_dump/pg_restore error output can echo the connection string
        # they were given; never print stdout/stderr, only the exit code.
        raise RehearsalError(
            f"{name} failed: {Path(error.cmd[0]).name} exited {error.returncode}. "
            "The target was disposable and has been removed."
        ) from error
    except SQLAlchemyError as error:
        raise RehearsalError(
            f"{name} failed with a database error ({type(error).__name__}). The target was disposable "
            "and has been removed."
        ) from error
    print(f"PASS {name}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument(
        "--postgres",
        action="store_true",
        help="use pg_dump/pg_restore against the explicitly confirmed disposable rehearsal PostgreSQL server",
    )
    args = parser.parse_args()
    operation = _postgres_backup_restore if args.postgres else _sqlite_backup_restore
    label = "PostgreSQL (pg_dump/pg_restore)" if args.postgres else "SQLite (file copy)"
    print(f"Starting {label} backup/restore rehearsal on self-created disposable targets.")
    try:
        _run("seed -> backup -> restore into a clean target -> verify integrity and ownership", operation)
    except RehearsalError as error:
        print(f"FAIL backup/restore rehearsal: {error}")
        return 1
    print("PASS backup/restore rehearsal completed; disposable targets were removed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
