"""List waitlist signups, newest first (#334).

No admin UI for v1, matching issue_invite.py's own scope -- this is the
owner's review step before deciding who to issue an invite to next.

    python scripts/list_waitlist.py
    python scripts/list_waitlist.py --csv > waitlist.csv
"""

from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--csv", action="store_true", help="Write CSV to stdout instead of a human-readable table.")
    args = parser.parse_args()

    from sqlalchemy import select

    from app.core.database import SessionLocal
    from app.models.waitlist_entry import WaitlistEntry

    with SessionLocal() as session:
        entries = session.scalars(select(WaitlistEntry).order_by(WaitlistEntry.created_at.desc())).all()

    if args.csv:
        writer = csv.writer(sys.stdout)
        writer.writerow(["created_at", "email", "name"])
        for entry in entries:
            writer.writerow([entry.created_at.isoformat(), entry.email, entry.name or ""])
        return 0

    if not entries:
        print("No waitlist signups yet.")
        return 0

    for entry in entries:
        print(f"{entry.created_at.isoformat()}  {entry.email}  {entry.name or ''}".rstrip())
    print(f"\n{len(entries)} total.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
