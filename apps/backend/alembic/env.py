from logging.config import fileConfig
from pathlib import Path

from alembic import context
from sqlalchemy import engine_from_config, pool

from app.core.config import get_settings
from app.models.base import Base

config = context.config
settings = get_settings()
config.set_main_option("sqlalchemy.url", settings.database_url.replace("%", "%%"))
if settings.database_url.startswith("sqlite"):
    database_path = settings.database_url.replace("sqlite:///", "")
    if database_path and database_path != ":memory:":
        Path(database_path).parent.mkdir(parents=True, exist_ok=True)

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    context.configure(
        url=settings.database_url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        if connection.dialect.name == "sqlite":
            # SQLite refuses to toggle `PRAGMA foreign_keys` mid-transaction
            # (a documented no-op once a transaction is open), and Alembic's
            # own per-migration transaction is already open by the time a
            # revision's upgrade() runs. A migration that uses batch mode to
            # add a constraint to a table that another table already has a
            # deferred foreign key pointing at (e.g. #299's cyclic
            # repository_lineages <-> repositories relationship) drops and
            # recreates that table; SQLite's deferred-FK bookkeeping does not
            # correctly reconcile that recreation against the still-open
            # transaction, and a fully self-consistent final state still
            # fails at COMMIT with a generic "FOREIGN KEY constraint failed"
            # (verified: `PRAGMA foreign_key_check` reports no violation
            # immediately beforehand). Disabling enforcement here, before any
            # transaction opens, avoids this without weakening runtime
            # enforcement: every real application connection still gets
            # `PRAGMA foreign_keys=ON` via app.core.database's own
            # connect-event listener; this affects only the connection
            # Alembic itself uses while migrating.
            connection.exec_driver_sql("PRAGMA foreign_keys=OFF")
            connection.commit()
        context.configure(connection=connection, target_metadata=target_metadata)

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
