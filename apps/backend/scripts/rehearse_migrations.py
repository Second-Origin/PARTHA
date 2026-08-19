"""Rehearse PARTHA's Alembic chain on databases this command creates itself.

The command intentionally accepts no database URL. Its default target is a
temporary SQLite file. ``--postgres`` is opt-in and creates a uniquely named
database on a dedicated rehearsal server configured through the environment.
Neither mode can be pointed at an existing application database.
"""

from __future__ import annotations

import argparse
import os
import sys
import tempfile
import uuid
from collections.abc import Callable, Iterator
from contextlib import AbstractContextManager, contextmanager
from datetime import UTC, datetime
from pathlib import Path

from alembic import command
from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import MetaData, Table, create_engine, inspect, select
from sqlalchemy.engine import URL, Engine, make_url
from sqlalchemy.exc import SQLAlchemyError


BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

HEAD_REVISION = "0010_account_deletion"
REPRESENTATIVE_BASELINE = "0004_ai_provider_configs"
REQUIRED_HEAD_TABLES = {
    "users",
    "repositories",
    "ri_snapshots",
    "analysis_jobs",
    "ai_conversation_messages",
    "account_deletion_audits",
}


class RehearsalError(RuntimeError):
    """A safe-to-print rehearsal failure."""


def _alembic_config(database_url: str) -> Config:
    """Build Alembic config after selecting an isolated target."""

    os.environ["DATABASE_URL"] = database_url
    os.environ.setdefault("CORS_ORIGINS", "http://migration-rehearsal.invalid")
    from app.core import config as app_config

    app_config.get_settings.cache_clear()
    cfg = Config(str(BACKEND_ROOT / "alembic.ini"))
    cfg.set_main_option("script_location", str(BACKEND_ROOT / "alembic"))
    return cfg


def _revision(engine: Engine) -> str:
    version = Table("alembic_version", MetaData(), autoload_with=engine)
    with engine.connect() as connection:
        value = connection.scalar(select(version.c.version_num))
    if not isinstance(value, str):
        raise RehearsalError("Alembic did not record a revision.")
    return value


def _assert_head(engine: Engine) -> None:
    missing_tables = REQUIRED_HEAD_TABLES - set(inspect(engine).get_table_names())
    if missing_tables:
        raise RehearsalError(f"Head is missing required table(s): {', '.join(sorted(missing_tables))}.")
    actual_revision = _revision(engine)
    if actual_revision != HEAD_REVISION:
        raise RehearsalError(
            f"Alembic reached revision {actual_revision!r} but this script expects {HEAD_REVISION!r}. "
            "If a new migration was added, update HEAD_REVISION (and REQUIRED_HEAD_TABLES if the "
            "schema changed) in rehearse_migrations.py."
        )


def _assert_chain(cfg: Config) -> None:
    heads = ScriptDirectory.from_config(cfg).get_heads()
    if len(heads) != 1:
        raise RehearsalError(
            f"Expected exactly one Alembic head, found {len(heads)}: {', '.join(sorted(heads))}. "
            "Inspect the migration graph for an unintended branch before rehearsing."
        )
    if heads[0] != HEAD_REVISION:
        raise RehearsalError(
            f"Alembic head is {heads[0]!r} but this script expects {HEAD_REVISION!r}. "
            "If a new migration was added, update HEAD_REVISION (and REQUIRED_HEAD_TABLES if the "
            "schema changed) in rehearse_migrations.py."
        )


def _exercise_clean_chain(database_url: str) -> None:
    cfg = _alembic_config(database_url)
    _assert_chain(cfg)
    engine = create_engine(database_url)
    try:
        if inspect(engine).get_table_names():
            raise RehearsalError("A rehearsal target was unexpectedly non-empty; refusing to continue.")
        command.upgrade(cfg, "head")
        _assert_head(engine)

        # This proves revision mechanics only. It is safe because the target
        # is empty; it does not claim production downgrades preserve data.
        command.downgrade(cfg, "base")
        if "repositories" in inspect(engine).get_table_names():
            raise RehearsalError("Clean downgrade did not return the target to base.")
        command.upgrade(cfg, "head")
        _assert_head(engine)
    finally:
        engine.dispose()


def _insert_representative_0004_row(engine: Engine) -> str:
    """Insert an old-format repository row before the 0005 backfill."""

    repositories = Table("repositories", MetaData(), autoload_with=engine)
    repository_id = "10000000-0000-0000-0000-000000000322"
    now = datetime.now(UTC)
    with engine.begin() as connection:
        connection.execute(
            repositories.insert().values(
                id=repository_id,
                owner_id="00000000-0000-0000-0000-000000000000",
                name="representative-legacy-github-import",
                description=None,
                source="github",
                source_url="https://github.com/example/representative",
                branch="main",
                local_path="/rehearsal/legacy",
                size=0,
                file_count=0,
                status="completed",
                data_source="real",
                analysis_stage=None,
                analysis_progress=100,
                uploaded_at=now,
                analysed_at=now,
                error_message=None,
                file_tree=[],
                repo_metadata={"commitSha": "a" * 40, "intelligence": {"legacy": True}},
                created_at=now,
                updated_at=now,
            )
        )
    return repository_id


def _exercise_representative_baseline(database_url: str) -> None:
    cfg = _alembic_config(database_url)
    _assert_chain(cfg)
    engine = create_engine(database_url)
    try:
        if inspect(engine).get_table_names():
            raise RehearsalError("A rehearsal target was unexpectedly non-empty; refusing to continue.")
        command.upgrade(cfg, REPRESENTATIVE_BASELINE)
        if _revision(engine) != REPRESENTATIVE_BASELINE:
            raise RehearsalError("Could not prepare the representative supported baseline.")
        repository_id = _insert_representative_0004_row(engine)

        command.upgrade(cfg, "head")
        _assert_head(engine)
        repositories = Table("repositories", MetaData(), autoload_with=engine)
        with engine.connect() as connection:
            row = connection.execute(
                select(
                    repositories.c.revision_kind,
                    repositories.c.revision_value,
                    repositories.c.revision_ref,
                    repositories.c.repo_metadata,
                ).where(repositories.c.id == repository_id)
            ).one()
        if tuple(row[:3]) != ("git", "a" * 40, "refs/heads/main"):
            raise RehearsalError("The representative 0004 repository was not backfilled as expected.")
        if row.repo_metadata != {"commitSha": "a" * 40, "intelligence": {"legacy": True}}:
            raise RehearsalError("The representative legacy metadata was unexpectedly changed.")
    finally:
        engine.dispose()


@contextmanager
def _sqlite_target() -> Iterator[str]:
    with tempfile.TemporaryDirectory(prefix="partha-migration-rehearsal-") as temporary_directory:
        yield f"sqlite:///{(Path(temporary_directory) / 'rehearsal.db').as_posix()}"


def _postgres_rehearsal_url() -> URL:
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
def _postgres_target() -> Iterator[str]:
    admin_url = _postgres_rehearsal_url()
    database_name = f"partha_migration_rehearsal_{uuid.uuid4().hex}"
    engine = create_engine(admin_url, isolation_level="AUTOCOMMIT")
    created = False
    quoted_name = engine.dialect.identifier_preparer.quote(database_name)
    try:
        with engine.connect() as connection:
            connection.exec_driver_sql(f"CREATE DATABASE {quoted_name}")
        created = True
        yield admin_url.set(database=database_name).render_as_string(hide_password=False)
    finally:
        try:
            if created:
                with engine.connect() as connection:
                    connection.exec_driver_sql(f"DROP DATABASE IF EXISTS {quoted_name} WITH (FORCE)")
        except Exception as cleanup_error:
            # Never let a teardown failure replace or hide the original
            # exception being propagated through this `finally`, and always
            # still reach `engine.dispose()` below. Print the disposable
            # database's name (a random UUID, safe to print) so an operator
            # can find and drop it manually if this warning is seen.
            print(
                f"WARNING: failed to drop disposable rehearsal database {database_name} "
                f"({type(cleanup_error).__name__}); it may require manual cleanup.",
                file=sys.stderr,
            )
        finally:
            engine.dispose()


def _run_phase(
    name: str,
    operation: Callable[[str], None],
    target_factory: Callable[[], AbstractContextManager[str]],
) -> None:
    try:
        with target_factory() as database_url:
            operation(database_url)
    except RehearsalError:
        raise
    except SQLAlchemyError as error:
        # Database driver errors can embed the connection URL (and its
        # credentials) in their message, so only the exception type is
        # surfaced here. The target was disposable and has been removed.
        raise RehearsalError(
            f"{name} failed with a database error ({type(error).__name__}). The target was disposable; "
            "review the Alembic output above and the migration runbook before retrying."
        ) from error
    except Exception as error:
        # Anything other than a database-driver error cannot contain
        # connection credentials, so its message is safe to surface and is
        # far more useful for debugging a script or migration bug.
        raise RehearsalError(f"{name} failed with {type(error).__name__}: {error}") from error
    print(f"PASS {name}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--postgres",
        action="store_true",
        help="use a uniquely named database on the explicitly confirmed rehearsal PostgreSQL server",
    )
    args = parser.parse_args()
    target_factory = _postgres_target if args.postgres else _sqlite_target
    target_label = "PostgreSQL" if args.postgres else "SQLite"
    print(f"Starting {target_label} migration rehearsal on self-created disposable databases.")
    try:
        _run_phase("clean upgrade -> clean downgrade -> re-upgrade", _exercise_clean_chain, target_factory)
        _run_phase("representative 0004 baseline -> head", _exercise_representative_baseline, target_factory)
    except RehearsalError as error:
        print(f"FAIL migration rehearsal: {error}")
        return 1
    print("PASS migration rehearsal completed; disposable targets were removed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
