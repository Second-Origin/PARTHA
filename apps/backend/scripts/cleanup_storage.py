"""Report and reclaim disk PARTHA no longer needs (#485).

Three things accumulate on a self-hosted instance:

* facts of failed or cancelled analyses -- discarded automatically by the
  worker now, this script only sweeps any left from before that;
* repository directories under ``STORAGE_PATH/repositories`` whose repository
  no longer exists (an import that failed part way, a removed database row);
* free pages inside the SQLite file. SQLite reuses freed pages for new
  analyses but never gives them back to the operating system until VACUUM.

Nothing is deleted unless ``--apply`` is given; the default is a report.
Completed analyses and the repositories they belong to are never touched --
deleting an old repository (which removes its analysis) is a normal action in
the app, and how much history to keep is your call.

    python scripts/cleanup_storage.py                 # report only
    python scripts/cleanup_storage.py --apply         # purge + remove orphans
    python scripts/cleanup_storage.py --apply --vacuum   # also shrink the SQLite file
                                                         # (stop PARTHA first; needs free disk
                                                         #  about the size of the database)
"""

from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))


def _size(path: Path) -> int:
    return sum(item.stat().st_size for item in path.rglob("*") if item.is_file())


def _mb(size: int) -> str:
    return f"{size / 1_000_000:.1f} MB"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--apply", action="store_true", help="Actually delete; without it, report only.")
    parser.add_argument("--vacuum", action="store_true", help="With --apply on SQLite: VACUUM the database file.")
    args = parser.parse_args()

    from sqlalchemy import exists, func, select, text

    from app.core.config import get_settings
    from app.core.database import SessionLocal, engine
    from app.intelligence.retention import purge_orphaned_failed_facts
    from app.models import RepositoryRecord
    from app.models.snapshot import RiNode, RiObservation, RiSnapshot

    settings = get_settings()
    repositories_root = settings.storage_path / "repositories"

    with SessionLocal() as session:
        failed_with_facts = session.scalar(
            select(func.count())
            .select_from(RiSnapshot)
            .where(
                RiSnapshot.state == "failed",
                exists().where(RiNode.snapshot_id == RiSnapshot.snapshot_id)
                | exists().where(RiObservation.snapshot_id == RiSnapshot.snapshot_id),
            )
        )
        known_ids = set(session.scalars(select(RepositoryRecord.id)).all())

        orphans = (
            [path for path in sorted(repositories_root.iterdir()) if path.is_dir() and path.name not in known_ids]
            if repositories_root.exists()
            else []
        )
        orphan_bytes = sum(_size(path) for path in orphans)

        print(f"Failed analyses still holding facts: {failed_with_facts}")
        print(f"Repository directories with no repository: {len(orphans)} ({_mb(orphan_bytes)})")
        for path in orphans:
            print(f"  {path.name}")

        if not args.apply:
            print("\nReport only. Re-run with --apply to clean up.")
            return 0

        purged = 0
        while True:
            batch = purge_orphaned_failed_facts(session)
            if not batch:
                break
            purged += batch
        print(f"\nDiscarded {purged} fact rows of failed analyses.")
        for path in orphans:
            shutil.rmtree(path, ignore_errors=True)
        print(f"Removed {len(orphans)} orphaned repository directories.")

    if args.vacuum:
        if engine.dialect.name != "sqlite":
            print("--vacuum applies to SQLite only; PostgreSQL reclaims space through autovacuum.")
        else:
            with engine.connect().execution_options(isolation_level="AUTOCOMMIT") as connection:
                connection.execute(text("VACUUM"))
            print("Vacuumed the SQLite database.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
