import os
import subprocess
import sys
from pathlib import Path


BACKEND_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = BACKEND_ROOT / "scripts" / "rehearse_migrations.py"


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
        "PARTHA_MIGRATION_REHEARSAL_PG_URL": "postgresql+psycopg://should-not-appear@db.example.invalid/postgres",
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
