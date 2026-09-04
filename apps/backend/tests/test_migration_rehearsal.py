import importlib.util
import os
import subprocess
import sys
from contextlib import contextmanager
from pathlib import Path

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url


BACKEND_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = BACKEND_ROOT / "scripts" / "rehearse_migrations.py"
PG_URL = os.environ.get("PARTHA_TEST_PG_URL")


def _load_rehearsal_module():
    """Import rehearse_migrations.py directly so its internals are reachable.

    scripts/ is a standalone maintainer command, not a package, so this
    loads it by path the same way the tests below invoke it by path.
    """

    spec = importlib.util.spec_from_file_location("rehearse_migrations", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_migration_rehearsal_runs_clean_and_representative_paths():
    result = subprocess.run(
        [sys.executable, str(SCRIPT)],
        cwd=BACKEND_ROOT,
        capture_output=True,
        text=True,
        check=False,
        env={**os.environ, "PARTHA_MIGRATION_REHEARSAL_PG_URL": ""},
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert "PASS clean upgrade -> clean downgrade -> re-upgrade" in result.stdout
    assert "PASS representative 0004 baseline -> head" in result.stdout
    assert "PASS migration rehearsal completed; disposable targets were removed." in result.stdout


def test_postgres_rehearsal_requires_explicit_disposable_confirmation():
    environment = {
        **os.environ,
        "PARTHA_MIGRATION_REHEARSAL_CONFIRM": "",
        "PARTHA_MIGRATION_REHEARSAL_PG_URL": "postgresql+psycopg://should-not-appear:should-not-appear@db.example.invalid/postgres",
    }
    result = subprocess.run(
        [sys.executable, str(SCRIPT), "--postgres"],
        cwd=BACKEND_ROOT,
        capture_output=True,
        text=True,
        check=False,
        env=environment,
    )

    assert result.returncode == 1
    assert "PARTHA_MIGRATION_REHEARSAL_CONFIRM=disposable" in result.stdout
    assert "should-not-appear" not in result.stdout + result.stderr


def test_postgres_rehearsal_requires_pg_url_when_confirmed():
    environment = {
        **os.environ,
        "PARTHA_MIGRATION_REHEARSAL_CONFIRM": "disposable",
        "PARTHA_MIGRATION_REHEARSAL_PG_URL": "",
    }
    result = subprocess.run(
        [sys.executable, str(SCRIPT), "--postgres"],
        cwd=BACKEND_ROOT,
        capture_output=True,
        text=True,
        check=False,
        env=environment,
    )

    assert result.returncode == 1
    assert "PARTHA_MIGRATION_REHEARSAL_PG_URL" in result.stdout


def test_postgres_rehearsal_rejects_non_postgresql_url():
    environment = {
        **os.environ,
        "PARTHA_MIGRATION_REHEARSAL_CONFIRM": "disposable",
        "PARTHA_MIGRATION_REHEARSAL_PG_URL": "sqlite:///should-not-be-used.db",
    }
    result = subprocess.run(
        [sys.executable, str(SCRIPT), "--postgres"],
        cwd=BACKEND_ROOT,
        capture_output=True,
        text=True,
        check=False,
        env=environment,
    )

    assert result.returncode == 1
    assert "must be a PostgreSQL URL" in result.stdout


def test_postgres_rehearsal_redacts_credentials_on_a_real_connection_failure():
    """A genuine (not just confirmation-gated) failure must still redact the URL.

    Unlike the confirmation test above, this uses a syntactically valid
    PostgreSQL URL pointed at an unresolvable host, so the script actually
    reaches the connection/redaction code path in `_run_phase` rather than
    short-circuiting before ever reading the URL.
    """

    environment = {
        **os.environ,
        "PARTHA_MIGRATION_REHEARSAL_CONFIRM": "disposable",
        "PARTHA_MIGRATION_REHEARSAL_PG_URL": (
            "postgresql+psycopg://rehearsal-user:should-not-appear-in-output@db.example.invalid/postgres"
        ),
    }
    result = subprocess.run(
        [sys.executable, str(SCRIPT), "--postgres"],
        cwd=BACKEND_ROOT,
        capture_output=True,
        text=True,
        check=False,
        env=environment,
        timeout=60,
    )

    assert result.returncode == 1
    combined_output = result.stdout + result.stderr
    assert "should-not-appear-in-output" not in combined_output
    assert "db.example.invalid" not in combined_output
    assert "failed with a database error" in result.stdout


def test_generic_rehearsal_failure_does_not_print_exception_message():
    rehearsal = _load_rehearsal_module()
    secret = "postgresql+psycopg://user:should-not-appear@private.example.invalid/postgres"

    @contextmanager
    def target():
        yield "sqlite:///:memory:"

    def operation(_database_url):
        raise RuntimeError(secret)

    with pytest.raises(rehearsal.RehearsalError) as captured:
        rehearsal._run_phase("forced generic failure", operation, target)

    rendered = str(captured.value)
    assert "RuntimeError" in rendered
    assert "should-not-appear" not in rendered
    assert "private.example.invalid" not in rendered


def test_main_fails_when_successful_rehearsal_cannot_clean_up(monkeypatch, capsys, tmp_path):
    rehearsal = _load_rehearsal_module()

    @contextmanager
    def target():
        yield f"sqlite:///{(tmp_path / 'cleanup-failure.db').as_posix()}"
        raise rehearsal.RehearsalError("forced cleanup failure")

    monkeypatch.setattr(rehearsal, "_postgres_target", target)
    monkeypatch.setattr(sys, "argv", [str(SCRIPT), "--postgres"])

    assert rehearsal.main() == 1
    output = capsys.readouterr()
    assert "FAIL migration rehearsal: forced cleanup failure" in output.out
    assert "PASS migration rehearsal completed; disposable targets were removed." not in output.out


@pytest.mark.skipif(not PG_URL, reason="set PARTHA_TEST_PG_URL to run the Postgres cleanup test")
def test_postgres_target_drops_disposable_database_when_the_operation_fails(monkeypatch):
    """The disposable database must not be leaked when rehearsal work fails.

    This is the core safety property #322 asks for: a failed rehearsal must
    never leave a database behind on the rehearsal server. It exercises
    `_postgres_target` directly (skipping Alembic) so the failure is
    deterministic rather than depending on a real migration bug.
    """

    rehearsal = _load_rehearsal_module()
    monkeypatch.setenv("PARTHA_MIGRATION_REHEARSAL_CONFIRM", "disposable")
    monkeypatch.setenv("PARTHA_MIGRATION_REHEARSAL_PG_URL", PG_URL)

    admin_engine = create_engine(make_url(PG_URL), isolation_level="AUTOCOMMIT")

    class _ForcedFailure(RuntimeError):
        pass

    captured_database_url = {}

    try:
        with pytest.raises(_ForcedFailure):
            with rehearsal._postgres_target() as database_url:
                captured_database_url["url"] = database_url
                raise _ForcedFailure("forced failure to prove disposable-database cleanup")

        disposable_database_name = make_url(captured_database_url["url"]).database
        with admin_engine.connect() as connection:
            still_exists = connection.scalar(
                text("SELECT 1 FROM pg_database WHERE datname = :name"),
                {"name": disposable_database_name},
            )
        assert still_exists is None, (
            f"disposable rehearsal database {disposable_database_name!r} was not "
            "cleaned up after the rehearsal operation failed"
        )
    finally:
        admin_engine.dispose()


@pytest.mark.skipif(not PG_URL, reason="set PARTHA_TEST_PG_URL to run the Postgres cleanup test")
def test_postgres_target_disposes_engine_even_when_cleanup_fails(monkeypatch):
    """A DROP DATABASE failure during teardown must not prevent engine.dispose().

    This forces the exact failure mode the cleanup fix guards against: the
    script's own DROP DATABASE call raises, and `engine.dispose()` must
    still run afterward instead of being skipped.
    """

    rehearsal = _load_rehearsal_module()
    from sqlalchemy.engine import Connection

    original_exec_driver_sql = Connection.exec_driver_sql
    call_state = {"failed_once": False}

    def _flaky_exec_driver_sql(self, statement, *args, **kwargs):
        if (
            isinstance(statement, str)
            and statement.strip().upper().startswith("DROP DATABASE")
            and not call_state["failed_once"]
        ):
            call_state["failed_once"] = True
            raise RuntimeError("forced DROP DATABASE failure for test")
        return original_exec_driver_sql(self, statement, *args, **kwargs)

    monkeypatch.setattr(Connection, "exec_driver_sql", _flaky_exec_driver_sql)

    disposed = {"called": False}
    real_create_engine = rehearsal.create_engine

    def _tracking_create_engine(*args, **kwargs):
        engine = real_create_engine(*args, **kwargs)
        original_dispose = engine.dispose

        def _tracking_dispose(*dispose_args, **dispose_kwargs):
            disposed["called"] = True
            return original_dispose(*dispose_args, **dispose_kwargs)

        engine.dispose = _tracking_dispose
        return engine

    monkeypatch.setattr(rehearsal, "create_engine", _tracking_create_engine)
    monkeypatch.setenv("PARTHA_MIGRATION_REHEARSAL_CONFIRM", "disposable")
    monkeypatch.setenv("PARTHA_MIGRATION_REHEARSAL_PG_URL", PG_URL)

    disposable_database_name = None
    try:
        with pytest.raises(rehearsal.RehearsalError, match="Cleanup failed"):
            with rehearsal._postgres_target() as database_url:
                disposable_database_name = make_url(database_url).database
        assert disposed["called"], "engine.dispose() was skipped when DROP DATABASE cleanup failed"
    finally:
        # The forced failure only trips on the first DROP DATABASE call
        # (the script's own attempt), so this cleanup call succeeds and
        # doesn't leave the disposable database behind.
        if disposable_database_name:
            admin_engine = create_engine(make_url(PG_URL), isolation_level="AUTOCOMMIT")
            try:
                quoted = admin_engine.dialect.identifier_preparer.quote(disposable_database_name)
                with admin_engine.connect() as connection:
                    connection.exec_driver_sql(f"DROP DATABASE IF EXISTS {quoted} WITH (FORCE)")
            finally:
                admin_engine.dispose()
