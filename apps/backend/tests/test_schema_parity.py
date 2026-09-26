"""A fresh ``create_all`` database and a fresh migrated one have the same schema (#483).

Both paths are live: ``create_all`` builds a brand-new database at startup,
while every upgrade runs the migrations. When they drift, the same code runs
against different constraints and indexes depending on how the database was
first created (a missing UNIQUE, indexes only one path builds).
"""

from __future__ import annotations

from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect

import app.models  # noqa: F401  (registers every model on Base.metadata)
from app.models.base import Base

BACKEND_ROOT = Path(__file__).resolve().parents[1]


#: ``repositories`` and ``repository_lineages`` reference each other, and
#: SQLite cannot add a foreign key after the fact. ``create_all`` on SQLite
#: therefore cannot be relied on to emit either table's foreign keys (it
#: resolves the cycle by leaving some out, and which ones is not stable from
#: one run to the next); the models document this as a ``create_all``-only
#: bootstrap gap (see ``RepositoryLineage.fk_repository_lineages_latest_member``).
#: Their foreign keys are asserted on the migrated side below instead, which
#: is the schema every real deployment has.
_CYCLIC_FK_TABLES = frozenset({"repositories", "repository_lineages"})


def _snapshot(engine) -> dict[str, dict[str, object]]:
    inspector = inspect(engine)
    schema: dict[str, dict[str, object]] = {}
    for table in sorted(set(inspector.get_table_names()) - {"alembic_version"}):
        schema[table] = {
            "columns": {
                column["name"]: (str(column["type"]), bool(column["nullable"]))
                for column in inspector.get_columns(table)
            },
            "primary_key": tuple(inspector.get_pk_constraint(table)["constrained_columns"]),
            "indexes": sorted(
                (index["name"], tuple(index["column_names"]), bool(index["unique"]))
                for index in inspector.get_indexes(table)
            ),
            "uniques": sorted(
                (constraint["name"], tuple(constraint["column_names"]))
                for constraint in inspector.get_unique_constraints(table)
            ),
            "foreign_keys": sorted(
                (
                    tuple(key["constrained_columns"]),
                    key["referred_table"],
                    tuple(key["referred_columns"]),
                    key["options"].get("ondelete"),
                )
                for key in inspector.get_foreign_keys(table)
            ),
        }
    return schema


@pytest.fixture()
def schemas(tmp_path, monkeypatch):
    created_url = f"sqlite:///{tmp_path / 'created.db'}"
    migrated_url = f"sqlite:///{tmp_path / 'migrated.db'}"

    created = create_engine(created_url)
    Base.metadata.create_all(created)

    monkeypatch.setenv("DATABASE_URL", migrated_url)
    monkeypatch.setenv("APP_ENV", "test")
    from app.core import config as app_config

    app_config.get_settings.cache_clear()
    config = Config(str(BACKEND_ROOT / "alembic.ini"))
    config.set_main_option("script_location", str(BACKEND_ROOT / "alembic"))
    command.upgrade(config, "head")
    migrated = create_engine(migrated_url)
    try:
        yield _snapshot(created), _snapshot(migrated)
    finally:
        created.dispose()
        migrated.dispose()
        app_config.get_settings.cache_clear()


def test_both_paths_create_the_same_tables(schemas):
    created, migrated = schemas

    # A migrated database that came out empty would make every comparison
    # below vacuous, so say so explicitly.
    assert migrated, "the migrated database has no tables"
    assert sorted(created) == sorted(migrated)


def test_every_table_has_the_same_columns_keys_indexes_and_constraints(schemas):
    created, migrated = schemas

    def comparable(schema: dict[str, object], table: str) -> dict[str, object]:
        aspects = dict(schema)
        if table in _CYCLIC_FK_TABLES:
            aspects.pop("foreign_keys")
        return aspects

    differences = {}
    for table in sorted(set(created) & set(migrated)):
        left, right = comparable(created[table], table), comparable(migrated[table], table)
        if left != right:
            differences[table] = {
                aspect: {"create_all": left[aspect], "migrations": right[aspect]}
                for aspect in left
                if left[aspect] != right[aspect]
            }

    assert differences == {}


def test_the_migrated_schema_has_the_cyclic_lineage_foreign_keys(schemas):
    _, migrated = schemas

    repositories = {(key[0], key[1]) for key in migrated["repositories"]["foreign_keys"]}
    lineages = {(key[0], key[1]) for key in migrated["repository_lineages"]["foreign_keys"]}

    assert (("lineage_id", "owner_id"), "repository_lineages") in repositories
    assert (("latest_repository_id", "id"), "repositories") in lineages
