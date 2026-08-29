"""Approve an email address for registration (#374).

Replaces the retired single-use invite codes (#341): access during the
invite-only beta is now gated by an admin-managed allowlist instead, and
this script is the v1 mechanism for adding to it -- there is no admin UI or
API route for this, matching the same scope the retired invite-issuing
script had.

An approved email is not a scarce secret and is not consumed by use: it
stays approved indefinitely (re-registering the same email a second time is
already rejected by the normal email-uniqueness check, regardless of this
table), so approving the same address twice is a harmless no-op, not an
error.

    python scripts/approve_email.py --email jane@example.com --note "waitlist: 2026-08-29"
    python scripts/approve_email.py --email jane@example.com --added-by parth
"""

from __future__ import annotations

import argparse
import getpass
import sys
from pathlib import Path
from uuid import uuid4

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--email", required=True, help="The email address to approve for registration.")
    parser.add_argument(
        "--note",
        default=None,
        help="Optional operator-only label (e.g. which waitlist entry this is for). Never shown to the registrant.",
    )
    parser.add_argument(
        "--added-by",
        default=None,
        help="Optional operator-only label for who ran this (defaults to the current OS user).",
    )
    args = parser.parse_args()

    from sqlalchemy import select

    from app.core.database import SessionLocal
    from app.models.approved_email import ApprovedEmail

    normalized = args.email.strip().lower()
    added_by = args.added_by or getpass.getuser()

    with SessionLocal() as session:
        existing = session.scalars(select(ApprovedEmail).where(ApprovedEmail.email == normalized)).first()
        if existing is not None:
            print(f"{normalized} is already approved (added {existing.created_at.isoformat()}).")
            return 0

        session.add(ApprovedEmail(id=str(uuid4()), email=normalized, note=args.note, added_by=added_by))
        session.commit()

    print(f"Approved {normalized}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
