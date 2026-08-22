"""Issue a single-use invite code for registration (#341).

Prints the raw code to stdout -- this is the only time it is ever visible.
Only its sha256 hash is stored, the same construction as refresh tokens, so
there is no way to recover a lost code; issue a new one instead.

    python scripts/issue_invite.py --note "waitlist: jane@example.com"
"""

from __future__ import annotations

import argparse
import secrets
import sys
from pathlib import Path
from uuid import uuid4

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument(
        "--note",
        default=None,
        help="Optional operator-only label (e.g. which waitlist entry this is for). Never shown to the registrant.",
    )
    args = parser.parse_args()

    from app.auth.security import hash_invite_code
    from app.core.database import SessionLocal
    from app.models.invite_token import InviteToken

    raw_code = secrets.token_urlsafe(24)
    with SessionLocal() as session:
        session.add(InviteToken(id=str(uuid4()), code_hash=hash_invite_code(raw_code), note=args.note))
        session.commit()

    print(raw_code)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
