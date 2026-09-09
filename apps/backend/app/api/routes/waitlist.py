from typing import Annotated
from uuid import uuid4

from fastapi import APIRouter, Body, Depends, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.openapi import documented_responses
from app.core.database import get_db
from app.models.waitlist_entry import WaitlistEntry
from app.schemas.waitlist import WaitlistSignupRequest, WaitlistSignupResponse

# Deliberately no auth dependency: this is the one public-facing write route
# in the API, reachable from the landing page before anyone has an account
# or an invite. Its own per-minute budget in the "auth" rate-limit class is
# the abuse guard.
router = APIRouter(prefix="/waitlist", tags=["waitlist"])

_SIGNUP_EXAMPLE = {
    "summary": "Join the waitlist",
    "value": {"email": "interested@example.com", "name": "Jane Doe"},
}
_RESPONSE_EXAMPLE = {"status": "ok"}


@router.post(
    "",
    response_model=WaitlistSignupResponse,
    status_code=status.HTTP_201_CREATED,
    responses=documented_responses(
        status.HTTP_201_CREATED,
        "Recorded. The same response is returned whether or not this email had already signed up.",
        _RESPONSE_EXAMPLE,
        422,
        429,
        500,
    ),
)
def join_waitlist(
    request: Annotated[WaitlistSignupRequest, Body(openapi_examples={"signup": _SIGNUP_EXAMPLE})],
    db: Session = Depends(get_db),
) -> WaitlistSignupResponse:
    normalized = request.email.strip().lower()
    existing = db.scalars(select(WaitlistEntry).where(WaitlistEntry.email == normalized)).first()
    if existing is None:
        db.add(WaitlistEntry(id=str(uuid4()), email=normalized, name=(request.name or "").strip() or None))
        try:
            db.commit()
        except IntegrityError:
            # A concurrent signup for the same email landed between the
            # check above and this insert -- the row exists either way, so
            # this is still a success from the caller's point of view, not
            # an error to surface.
            db.rollback()
    # Same response for a brand-new signup, a repeat signup, and a
    # concurrent-collision signup: never discloses which case occurred, and
    # a visitor resubmitting the form never sees an error (#334).
    return WaitlistSignupResponse(status="ok")
