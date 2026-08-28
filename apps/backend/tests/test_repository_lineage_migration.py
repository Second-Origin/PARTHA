"""Migration-level coverage for #299 (RFC-0002), revisions 0013/0014.

Covers the plan's §13 "Migration tests" matrix: fresh empty DB shape, a
populated DB with the exact grouping/exclusion cases the backfill must get
right, deterministic tie-breaks, idempotent rerun, and full downgrade/
upgrade round trips on both SQLite and (when ``PARTHA_TEST_PG_URL`` is set)
real PostgreSQL.
"""

import importlib.util
import os
import uuid
from datetime import UTC, datetime, timedelta
from types import ModuleType

import pytest
from alembic import command
from alembic.config import Config
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import MetaData, Table, create_engine, inspect, select
from sqlalchemy.engine import make_url

from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
PG_URL = os.environ.get("PARTHA_TEST_PG_URL")


def _alembic_config() -> Config:
    cfg = Config(str(BACKEND_ROOT / "alembic.ini"))
    cfg.set_main_option("script_location", str(BACKEND_ROOT / "alembic"))
    return cfg


def _load_migration_module(revision_filename: str) -> ModuleType:
    """Load a migration script's own module so its private helper functions
    (e.g. ``_backfill_lineages``) can be called directly in a test, the same
    way Alembic itself loads and executes it -- not via a package import,
    since revision modules are not importable by their filename (it starts
    with a digit) and are never meant to be imported by application code."""
    path = BACKEND_ROOT / "alembic" / "versions" / f"{revision_filename}.py"
    spec = importlib.util.spec_from_file_location(revision_filename, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _database_url(tmp_path) -> str:
    if not PG_URL:
        return f"sqlite:///{tmp_path / 'lineage-migration.db'}"
    admin_url = make_url(PG_URL)
    database_name = f"partha_lineage_migration_{uuid.uuid4().hex}"
    admin_engine = create_engine(admin_url, isolation_level="AUTOCOMMIT")
    try:
        with admin_engine.connect() as connection:
            connection.exec_driver_sql(f'CREATE DATABASE "{database_name}"')
    finally:
        admin_engine.dispose()
    return admin_url.set(database=database_name).render_as_string(hide_password=False)


def _drop_pg_database(database_url: str) -> None:
    if not PG_URL:
        return
    admin_url = make_url(PG_URL)
    target = make_url(database_url)
    admin_engine = create_engine(admin_url, isolation_level="AUTOCOMMIT")
    try:
        with admin_engine.connect() as connection:
            connection.exec_driver_sql(f'DROP DATABASE IF EXISTS "{target.database}" WITH (FORCE)')
    finally:
        admin_engine.dispose()


@pytest.fixture()
def lineage_migration_db(tmp_path, monkeypatch):
    # Import for its side effect: registers the `PRAGMA foreign_keys=ON`
    # connect-event listener on the SQLAlchemy Engine class globally (see
    # app/core/database.py). Without this import having already happened
    # somewhere in the process, SQLite silently never enforces any foreign
    # key at all -- these migration tests would then "pass" while proving
    # nothing about the cyclic FK's actual behavior, exactly as happened
    # once during development (caught only by incidental test-file
    # ordering in a full-suite run, not by this file in isolation). Forcing
    # it here makes that guarantee deterministic instead of accidental.
    import app.core.database  # noqa: F401

    database_url = _database_url(tmp_path)
    monkeypatch.setenv("DATABASE_URL", database_url)
    monkeypatch.setenv("CORS_ORIGINS", "http://testserver")
    from app.core import config

    config.get_settings.cache_clear()
    engine = create_engine(database_url)
    try:
        yield database_url, engine
    finally:
        engine.dispose()
        config.get_settings.cache_clear()
        _drop_pg_database(database_url)


def test_fresh_database_reaches_head_with_the_expected_lineage_shape(lineage_migration_db):
    database_url, engine = lineage_migration_db
    cfg = _alembic_config()

    command.upgrade(cfg, "head")

    insp = inspect(engine)
    assert "repository_lineages" in insp.get_table_names()

    lineage_columns = {column["name"] for column in insp.get_columns("repository_lineages")}
    assert lineage_columns == {
        "id",
        "owner_id",
        "canonical_source_key",
        "canonical_branch",
        "display_name",
        "latest_repository_id",
        "next_sequence",
        "created_at",
    }

    repo_columns = {column["name"] for column in insp.get_columns("repositories")}
    assert {"lineage_id", "sequence"} <= repo_columns

    repo_fk_names = {fk["name"] for fk in insp.get_foreign_keys("repositories")}
    assert "fk_repositories_lineage_owner" in repo_fk_names
    lineage_fk_names = {fk["name"] for fk in insp.get_foreign_keys("repository_lineages")}
    assert {"fk_repository_lineages_owner_id_users", "fk_repository_lineages_latest_member"} <= lineage_fk_names

    latest_member_fk = next(
        fk
        for fk in insp.get_foreign_keys("repository_lineages")
        if fk["name"] == "fk_repository_lineages_latest_member"
    )
    assert latest_member_fk["constrained_columns"] == ["latest_repository_id", "id"]
    assert latest_member_fk["referred_columns"] == ["id", "lineage_id"]
    assert latest_member_fk["options"].get("deferrable") is True

    repo_uk_names = {uk["name"] for uk in insp.get_unique_constraints("repositories")}
    assert {"uq_repositories_lineage_sequence", "uq_repositories_id_lineage"} <= repo_uk_names

    index_names = {index["name"] for index in insp.get_indexes("repository_lineages")}
    assert "uq_repository_lineages_owner_source_branch" in index_names
    assert "ix_repository_lineages_owner_id" in index_names

    command.downgrade(cfg, "base")
    assert "repository_lineages" not in inspect(engine).get_table_names()

    command.upgrade(cfg, "head")
    assert "repository_lineages" in inspect(engine).get_table_names()


def _seed_users_and_repositories(engine, rows: list[dict]) -> tuple[str, str]:
    """Insert two users and the given legacy-shaped repository rows at 0012,
    before 0013/0014 exist. Returns (owner_a, owner_b)."""
    meta = MetaData()
    users = Table("users", meta, autoload_with=engine)
    repositories = Table("repositories", meta, autoload_with=engine)

    owner_a = str(uuid.uuid4())
    owner_b = str(uuid.uuid4())
    now = datetime.now(UTC)
    with engine.begin() as connection:
        connection.execute(
            users.insert(),
            [
                {
                    "id": owner_a,
                    "email": f"a-{uuid.uuid4().hex}@example.com",
                    "is_active": True,
                    "created_at": now,
                    "updated_at": now,
                    "password_hash": None,
                },
                {
                    "id": owner_b,
                    "email": f"b-{uuid.uuid4().hex}@example.com",
                    "is_active": True,
                    "created_at": now,
                    "updated_at": now,
                    "password_hash": None,
                },
            ],
        )
        if rows:
            connection.execute(repositories.insert(), rows)
    return owner_a, owner_b


def _repo_row(owner_id: str, **overrides) -> dict:
    now = datetime.now(UTC)
    base = dict(
        id=str(uuid.uuid4()),
        owner_id=owner_id,
        name="demo",
        description=None,
        source="github",
        source_url="https://github.com/acme/widgets",
        branch="main",
        local_path="/x",
        size=0,
        file_count=1,
        status="completed",
        analysis_stage=None,
        analysis_progress=100,
        uploaded_at=now,
        analysed_at=now,
        error_message=None,
        repo_metadata=None,
        file_tree=[],
        created_at=now,
        updated_at=now,
        revision_kind="git",
        revision_value="a" * 40,
        revision_ref="refs/heads/main",
    )
    base.update(overrides)
    return base


def test_backfill_groups_correctly_and_leaves_ineligible_rows_standalone(lineage_migration_db):
    """One populated-DB test exercising every §6 grouping/exclusion case at
    once: same source/ref groups; different ref, different repo, and
    different owner each get a separate lineage; a URL variant (mixed-case
    host, .git suffix, trailing slash) still canonicalizes into the same
    lineage; a malformed URL, an unresolved ref, and an upload all stay
    standalone; and a deterministic timestamp tie breaks on repository id.
    """
    database_url, engine = lineage_migration_db
    cfg = _alembic_config()
    command.upgrade(cfg, "0012_waitlist_entries")

    now = datetime.now(UTC)
    owner_a, owner_b = _seed_users_and_repositories(engine, [])

    meta = MetaData()
    repositories = Table("repositories", meta, autoload_with=engine)

    group_first = str(uuid.uuid4())
    group_second = str(uuid.uuid4())
    variant_row_id = str(uuid.uuid4())
    dev_row_id = str(uuid.uuid4())
    other_owner_row_id = str(uuid.uuid4())
    malformed_row_id = str(uuid.uuid4())
    unresolved_row_id = str(uuid.uuid4())
    upload_row_id = str(uuid.uuid4())
    tie_a = "20000000-0000-0000-0000-000000000001"
    tie_b = "20000000-0000-0000-0000-000000000002"

    rows = [
        _repo_row(
            owner_a,
            id=group_first,
            revision_value="a" * 40,
            created_at=now - timedelta(days=2),
        ),
        _repo_row(
            owner_a,
            id=group_second,
            revision_value="b" * 40,
            created_at=now - timedelta(days=1),
        ),
        _repo_row(
            owner_a,
            id=variant_row_id,
            source_url="https://GitHub.com/Acme/Widgets.git/",
            revision_value="c" * 40,
            created_at=now,
        ),
        _repo_row(owner_a, id=dev_row_id, revision_ref="refs/heads/dev", revision_value="d" * 40, created_at=now),
        _repo_row(owner_b, id=other_owner_row_id, revision_value="e" * 40, created_at=now),
        _repo_row(owner_a, id=malformed_row_id, source_url="not a url at all", revision_value="f" * 40, created_at=now),
        _repo_row(
            owner_a,
            id=unresolved_row_id,
            source_url="https://github.com/acme/other",
            revision_ref=None,
            revision_value="1" * 40,
            created_at=now,
        ),
        dict(
            id=upload_row_id,
            owner_id=owner_a,
            name="upload1",
            description=None,
            source="upload",
            source_url=None,
            branch=None,
            local_path="/y",
            size=0,
            file_count=1,
            status="completed",
            analysis_stage=None,
            analysis_progress=100,
            uploaded_at=now,
            analysed_at=now,
            error_message=None,
            repo_metadata=None,
            file_tree=[],
            created_at=now,
            updated_at=now,
            revision_kind="upload",
            revision_value="sha256:" + "0" * 64,
            revision_ref=None,
        ),
        _repo_row(
            owner_a,
            id=tie_a,
            source_url="https://github.com/acme/tied",
            revision_value="2" * 40,
            created_at=now,
        ),
        _repo_row(
            owner_a,
            id=tie_b,
            source_url="https://github.com/acme/tied",
            revision_value="3" * 40,
            created_at=now,
        ),
    ]
    with engine.begin() as connection:
        connection.execute(repositories.insert(), rows)

    command.upgrade(cfg, "head")

    meta2 = MetaData()
    repos2 = Table("repositories", meta2, autoload_with=engine)
    lineages2 = Table("repository_lineages", meta2, autoload_with=engine)

    with engine.connect() as connection:
        attached = {
            row.id: (row.lineage_id, row.sequence)
            for row in connection.execute(select(repos2.c.id, repos2.c.lineage_id, repos2.c.sequence))
        }

        # The primary group: two original commits plus the URL-variant row,
        # in creation order.
        assert attached[group_first][1] == 1
        assert attached[group_second][1] == 2
        assert attached[variant_row_id][1] == 3
        primary_lineage = attached[group_first][0]
        assert attached[group_second][0] == primary_lineage
        assert attached[variant_row_id][0] == primary_lineage

        # A different ref is a different lineage.
        assert attached[dev_row_id][0] != primary_lineage
        assert attached[dev_row_id][1] == 1

        # A different owner is a different lineage, even for the same
        # canonical source/ref.
        assert attached[other_owner_row_id][0] != primary_lineage
        assert attached[other_owner_row_id][1] == 1

        # Ineligible rows stay standalone.
        assert attached[malformed_row_id] == (None, None)
        assert attached[unresolved_row_id] == (None, None)
        assert attached[upload_row_id] == (None, None)

        # Deterministic timestamp tie-break: identical created_at, so the
        # lexicographically smaller id (tie_a) gets sequence 1.
        assert attached[tie_a][1] == 1
        assert attached[tie_b][1] == 2
        assert attached[tie_a][0] == attached[tie_b][0]

        primary_row = (
            connection.execute(
                select(
                    lineages2.c.owner_id,
                    lineages2.c.canonical_source_key,
                    lineages2.c.canonical_branch,
                    lineages2.c.display_name,
                    lineages2.c.latest_repository_id,
                    lineages2.c.next_sequence,
                ).where(lineages2.c.id == primary_lineage)
            )
            .mappings()
            .one()
        )
        assert primary_row["owner_id"] == owner_a
        assert primary_row["canonical_source_key"] == "github.com/acme/widgets"
        assert primary_row["canonical_branch"] == "refs/heads/main"
        assert primary_row["display_name"] == "demo"
        assert primary_row["latest_repository_id"] == variant_row_id
        assert primary_row["next_sequence"] == 4

        # No stray lineage attachment anywhere else: exactly the 7 eligible
        # rows (group_first, group_second, variant, dev, other_owner, tie_a,
        # tie_b) carry a lineage, and every (lineage_id, sequence) pair is
        # unique.
        attachments = [
            (row.lineage_id, row.sequence)
            for row in connection.execute(select(repos2.c.lineage_id, repos2.c.sequence))
            if row.lineage_id is not None
        ]
        assert len(attachments) == 7
        assert len(set(attachments)) == 7

    command.downgrade(cfg, "base")
    command.upgrade(cfg, "head")


def test_backfill_rerun_is_idempotent(lineage_migration_db):
    """Calling the backfill helper twice against the same already-backfilled
    data reconciles to the identical final state rather than erroring or
    double-counting (plan §6.2/§7 "interruption and rerun")."""
    database_url, engine = lineage_migration_db
    cfg = _alembic_config()
    command.upgrade(cfg, "0012_waitlist_entries")

    owner_a, _owner_b = _seed_users_and_repositories(engine, [])
    meta = MetaData()
    repositories = Table("repositories", meta, autoload_with=engine)
    now = datetime.now(UTC)
    first_id, second_id = str(uuid.uuid4()), str(uuid.uuid4())
    with engine.begin() as connection:
        connection.execute(
            repositories.insert(),
            [
                _repo_row(owner_a, id=first_id, revision_value="a" * 40, created_at=now - timedelta(days=1)),
                _repo_row(owner_a, id=second_id, revision_value="b" * 40, created_at=now),
            ],
        )

    command.upgrade(cfg, "0013_lineage_expand")

    migration = _load_migration_module("0013_lineage_expand")

    with engine.connect() as connection:
        migration_context = MigrationContext.configure(connection)
        with connection.begin(), Operations.context(migration_context):
            groups_first = migration._backfill_lineages()
            migration._verify_backfill(groups_first)
            groups_second = migration._backfill_lineages()
            migration._verify_backfill(groups_second)

    meta2 = MetaData()
    repos2 = Table("repositories", meta2, autoload_with=engine)
    lineages2 = Table("repository_lineages", meta2, autoload_with=engine)
    with engine.connect() as connection:
        lineage_rows = connection.execute(select(lineages2.c.id, lineages2.c.next_sequence)).all()
        assert len(lineage_rows) == 1
        assert lineage_rows[0].next_sequence == 3

        sequences = sorted(
            row.sequence
            for row in connection.execute(select(repos2.c.sequence).where(repos2.c.id.in_([first_id, second_id])))
        )
        assert sequences == [1, 2]

    command.upgrade(cfg, "head")
    command.downgrade(cfg, "base")
