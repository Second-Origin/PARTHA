"""Development database schema-sync and drift detection (#166).

``AUTO_CREATE_TABLES``'s ``create_all`` creates any table missing from the
database but never alters an existing one and never advances the
``alembic_version`` stamp. After any schema-changing merge, an existing local
development database silently drifts from the code: requests fail at
runtime with opaque ``IntegrityError``/``OperationalError`` 500s instead of a
clear migration error. This module makes that drift visible -- and, in
development/test, self-heals it -- at startup instead of at request time.

Reads revisions through Alembic's ``ScriptDirectory``/``MigrationContext``
APIs and runs an upgrade through ``alembic.command.upgrade`` (the same
in-process Python API ``tests/test_migrations.py`` already uses); nothing
here shells out to the ``alembic`` CLI. Dialect-agnostic: SQLite and
PostgreSQL both pass through the same code path.
"""

from __future__ import annotations

import inspect
import logging
import re
from pathlib import Path

from alembic import command
from alembic.config import Config
from alembic.runtime.migration import MigrationContext
from alembic.script import ScriptDirectory
from sqlalchemy import inspect as sa_inspect
from sqlalchemy.engine import Engine

logger = logging.getLogger(__name__)

_BACKEND_ROOT = Path(__file__).resolve().parents[2]
_DEV_ENVS = frozenset({"development", "test"})
_CREATE_TABLE_PATTERN = re.compile(r'create_table\(\s*["\'](\w+)["\']')


class SchemaDriftError(RuntimeError):
    """The database schema cannot be safely reconciled automatically.

    Raised only for the case a blind ``alembic upgrade head`` cannot resolve
    on its own: a pending migration would create a table that already
    exists physically (built by a prior ``create_all`` run without a
    matching stamp). Auto-upgrading here would crash with "table already
    exists"; the caller should let this propagate so the app refuses to
    start with the actionable message it carries.
    """


def _alembic_config() -> Config:
    config = Config(str(_BACKEND_ROOT / "alembic.ini"))
    config.set_main_option("script_location", str(_BACKEND_ROOT / "alembic"))
    return config


def _script_directory() -> ScriptDirectory:
    return ScriptDirectory.from_config(_alembic_config())


def head_revision() -> str:
    heads = _script_directory().get_heads()
    if len(heads) != 1:
        raise SchemaDriftError(f"Expected exactly one Alembic head, found {heads!r}.")
    return heads[0]


def current_revision(engine: Engine) -> str | None:
    with engine.connect() as connection:
        return MigrationContext.configure(connection).get_current_revision()


def stamp_head(engine: Engine) -> None:
    """Stamp ``alembic_version`` at head without running any migration body.

    Used only right after ``Base.metadata.create_all`` builds every table
    directly from the current ORM models -- which by definition already
    matches head's shape -- so only the bookkeeping stamp needs to catch up,
    not any migration body.
    """

    script = _script_directory()
    head = head_revision()
    with engine.begin() as connection:
        MigrationContext.configure(connection).stamp(script, head)
    logger.info("Stamped fresh database at Alembic head %s", head)


def _tables_created_between(script: ScriptDirectory, head: str, lower: str) -> dict[str, str]:
    """Map table name -> revision id for every ``create_table`` after ``lower``.

    A static, cheap probe (no migration execution): reads each pending
    revision's ``upgrade()`` source text rather than running it.
    """

    created: dict[str, str] = {}
    for revision_script in script.iterate_revisions(head, lower):
        upgrade_source = inspect.getsource(revision_script.module.upgrade)
        for table_name in _CREATE_TABLE_PATTERN.findall(upgrade_source):
            created[table_name] = revision_script.revision
    return created


def _recommended_stamp(script: ScriptDirectory, head: str, lower: str, existing_tables: set[str]) -> str:
    """The latest pending revision whose created table(s) already exist physically.

    Walked oldest-first from ``lower``; only advances past a revision when its
    created table(s) are positively confirmed already present. A revision
    that creates no table at all (a pure column/index change, like a plain
    ``drop_column``) gives no physical evidence either way that it already
    ran, so it must not be silently assumed applied -- advancing past it
    would recommend stamping over a migration that never actually executed.
    Stops at the first revision without that positive confirmation.
    """

    recommended = lower
    for revision_script in reversed(list(script.iterate_revisions(head, lower))):
        upgrade_source = inspect.getsource(revision_script.module.upgrade)
        created = set(_CREATE_TABLE_PATTERN.findall(upgrade_source))
        if not created or not created.issubset(existing_tables):
            break
        recommended = revision_script.revision
    return recommended


def ensure_schema_in_sync(engine: Engine, *, app_env: str) -> None:
    """Detect and, in development/test, resolve local database schema drift.

    No-op outside development/test: production/staging behaviour is
    unchanged, migrations remain the operator's explicit responsibility
    there.

    When the database is genuinely behind head with no physical conflict,
    upgrades it in place (logging exactly what ran). When a pending
    migration would create a table that already exists physically --
    the create_all-without-stamp state -- raises ``SchemaDriftError`` with
    the stamp-then-upgrade recovery instead of attempting the upgrade, so a
    crash-loop on "table already exists" is never silently retried.
    """

    if app_env not in _DEV_ENVS:
        return

    script = _script_directory()
    head = head_revision()
    current = current_revision(engine)
    if current == head:
        return

    lower = current or "base"
    existing_tables = set(sa_inspect(engine).get_table_names())
    tables_by_revision = _tables_created_between(script, head, lower)
    conflicts = {
        table: revision for table, revision in tables_by_revision.items() if table in existing_tables
    }
    if conflicts:
        recommended = _recommended_stamp(script, head, lower, existing_tables)
        conflict_desc = ", ".join(f"{table!r} (from {revision})" for table, revision in sorted(conflicts.items()))
        raise SchemaDriftError(
            "Local database schema has drifted from its Alembic stamp: table(s) "
            f"{conflict_desc} already exist physically even though the database is "
            f"stamped at {current!r} (head is {head!r}). This happens when "
            "AUTO_CREATE_TABLES built a table without updating alembic_version. "
            "A blind 'alembic upgrade head' would crash trying to recreate it. "
            "Recover with:\n"
            f"  cd apps/backend && .venv/bin/alembic stamp {recommended}\n"
            "  cd apps/backend && .venv/bin/alembic upgrade head\n"
            "The first command marks the migrations already reflected in the physical "
            "schema as applied without re-running them; the second then applies whatever "
            "genuinely remains pending."
        )

    logger.warning(
        "Local database schema is behind Alembic head (%s -> %s); upgrading automatically.",
        current,
        head,
    )
    command.upgrade(_alembic_config(), "head")
    logger.info("Upgraded local database schema to Alembic head %s", head)
