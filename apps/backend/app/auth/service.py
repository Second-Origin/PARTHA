import logging
from datetime import UTC, datetime, timedelta
from uuid import uuid4

from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.auth.security import (
    burn_password_check,
    create_access_token,
    hash_password,
    hash_refresh_token,
    new_refresh_token,
    verify_password,
)
from app.core.config import Settings
from app.core.exceptions import ConflictServiceError, UnauthorizedError, ValidationServiceError
from app.models.approved_email import ApprovedEmail
from app.models.refresh_token import RefreshToken
from app.models.user import User

logger = logging.getLogger(__name__)

# Every credential failure returns this exact message so responses cannot be
# used to tell apart unknown email / wrong password / disabled account.
INVALID_CREDENTIALS = "Invalid email or password."
INVALID_REFRESH = "Invalid refresh token."
# #374: registration is gated by an admin-managed allowlist, not a secret --
# unlike the retired invite-code message, this can say exactly what's wrong,
# the same way the waitlist's own "we'll be in touch" framing does.
EMAIL_NOT_APPROVED = "This email hasn't been approved for access yet. Join the waitlist and we'll be in touch."


def _as_utc(value: datetime) -> datetime:
    # SQLite returns naive datetimes for DateTime(timezone=True) columns while
    # Postgres returns aware ones; normalize before comparing.
    return value if value.tzinfo is not None else value.replace(tzinfo=UTC)


class AuthService:
    def __init__(self, db: Session, settings: Settings) -> None:
        self.db = db
        self.settings = settings

    def register(self, email: str, password: str) -> tuple[User, str, str]:
        normalized = email.strip().lower()
        self._ensure_email_available(normalized)
        approval = self._require_approval(normalized)
        user = User(id=str(uuid4()), email=normalized, password_hash=hash_password(password))
        return self._create_approved_user(user, approval)

    def register_oauth_user(self, email: str) -> tuple[User, str, str]:
        """Create a brand-new, password-less account for a verified OAuth
        identity (OAuthService, #288/#374).

        Identical approval gate and audit trail as ``register()`` -- the
        allowlist is the single source of truth for who may ever get a new
        PARTHA account, regardless of which door (password or OAuth) they
        come through. The only difference from ``register()`` is that there
        is no password to hash.
        """
        normalized = email.strip().lower()
        self._ensure_email_available(normalized)
        approval = self._require_approval(normalized)
        user = User(id=str(uuid4()), email=normalized, password_hash=None)
        return self._create_approved_user(user, approval)

    def _ensure_email_available(self, normalized_email: str) -> None:
        existing = self.db.scalars(select(User).where(User.email == normalized_email)).first()
        if existing:
            raise ConflictServiceError("An account with this email already exists.")

    def _require_approval(self, normalized_email: str) -> ApprovedEmail:
        approval = self.db.scalars(select(ApprovedEmail).where(ApprovedEmail.email == normalized_email)).first()
        if approval is None:
            raise ValidationServiceError(EMAIL_NOT_APPROVED)
        return approval

    def _create_approved_user(self, user: User, approval: ApprovedEmail) -> tuple[User, str, str]:
        self.db.add(user)
        try:
            # Flushed here, ahead of commit, so a concurrent registration for
            # the same email surfaces here as an IntegrityError rather than
            # only at commit -- the identical handling is needed at both
            # points, since either can be where the race actually lands.
            self.db.flush()
        except IntegrityError:
            self.db.rollback()
            if self.db.scalars(select(User).where(User.email == user.email)).first() is not None:
                raise ConflictServiceError("An account with this email already exists.") from None
            raise

        # Purely informational (see ApprovedEmail's docstring) -- unlike the
        # retired invite-code redemption, this never gates anything and so
        # needs no atomic conditional UPDATE: the email-uniqueness check
        # above is what actually prevents two accounts for one email.
        approval.used_at = datetime.now(UTC)
        approval.used_by_user_id = user.id

        try:
            self.db.commit()
        except IntegrityError:
            # A second, unrelated integrity failure at commit time (the email
            # collision itself is already handled above, at flush) must still
            # not surface as a raw 500.
            self.db.rollback()
            if self.db.scalars(select(User).where(User.email == user.email)).first() is not None:
                raise ConflictServiceError("An account with this email already exists.") from None
            raise
        self.db.refresh(user)
        return self.open_session(user)

    def login(self, email: str, password: str) -> tuple[User, str, str]:
        normalized = email.strip().lower()
        user = self.db.scalars(select(User).where(User.email == normalized)).first()
        if user is None or user.password_hash is None:
            # Unknown accounts and credential-less accounts (e.g. the seed
            # user) cost one hash check, the same as a real login attempt.
            burn_password_check(password)
            raise UnauthorizedError(INVALID_CREDENTIALS)
        if not verify_password(user.password_hash, password):
            raise UnauthorizedError(INVALID_CREDENTIALS)
        if not user.is_active:
            raise UnauthorizedError(INVALID_CREDENTIALS)
        return self.open_session(user)

    def refresh(self, raw_token: str) -> tuple[User, str, str]:
        now = datetime.now(UTC)
        record = self.db.scalars(
            select(RefreshToken).where(RefreshToken.token_hash == hash_refresh_token(raw_token))
        ).first()
        if record is None or record.revoked_at is not None or _as_utc(record.expires_at) <= now:
            raise UnauthorizedError(INVALID_REFRESH)
        if record.used_at is not None:
            # A rotated token came back: someone is replaying it. Kill the
            # whole family so the holder of the successor is logged out too.
            self._revoke_family(record.family_id, now)
            logger.warning(
                "Refresh token reuse detected; family revoked",
                extra={"family_id": record.family_id, "user_id": record.user_id},
            )
            raise UnauthorizedError(INVALID_REFRESH)

        user = self.db.get(User, record.user_id)
        if user is None or not user.is_active:
            self._revoke_family(record.family_id, now)
            raise UnauthorizedError(INVALID_REFRESH)

        # Claim the token atomically. Two requests presenting the same token can
        # both pass the used_at check above (they read before either writes);
        # the UPDATE ... WHERE used_at IS NULL and the row lock it takes let only
        # one win. The loser is a concurrent replay, so it is handled like reuse.
        if not self._claim_token(record.id, now):
            self._revoke_family(record.family_id, now)
            logger.warning(
                "Concurrent refresh of a single token; family revoked",
                extra={"family_id": record.family_id, "user_id": record.user_id},
            )
            raise UnauthorizedError(INVALID_REFRESH)

        raw_successor = self._issue_refresh(user.id, record.family_id)
        self.db.commit()
        return user, create_access_token(user.id, self.settings), raw_successor

    def _claim_token(self, token_id: str, now: datetime) -> bool:
        """Mark a refresh token used, but only if it is not already used.

        Returns True for the single caller whose UPDATE affects the row and
        False for any concurrent caller. The atomic ``UPDATE ... WHERE used_at
        IS NULL`` is what makes rotation safe under real database concurrency,
        rather than the earlier read-then-write which two racers could both pass.
        """
        result = self.db.execute(
            update(RefreshToken).where(RefreshToken.id == token_id, RefreshToken.used_at.is_(None)).values(used_at=now)
        )
        return result.rowcount == 1

    def logout(self, raw_token: str | None) -> None:
        """Revoke the session family for the presented refresh token.

        Idempotent by design: logging out with a missing or unknown token is
        not an error, so repeated logouts and cleared cookies stay harmless.
        """
        if not raw_token:
            return
        record = self.db.scalars(
            select(RefreshToken).where(RefreshToken.token_hash == hash_refresh_token(raw_token))
        ).first()
        if record is None:
            return
        self._revoke_family(record.family_id, datetime.now(UTC))
        self.db.commit()

    def open_session(self, user: User) -> tuple[User, str, str]:
        """Issue a fresh refresh-token family and access token for `user`.

        Public so callers that authenticate a user by some means other than
        password login (OAuthService, #288) can reuse the exact same session
        primitive as register()/login() rather than duplicating it.
        """
        raw_refresh = self._issue_refresh(user.id, family_id=None)
        self.db.commit()
        return user, create_access_token(user.id, self.settings), raw_refresh

    def _issue_refresh(self, user_id: str, family_id: str | None) -> str:
        raw = new_refresh_token()
        self.db.add(
            RefreshToken(
                id=str(uuid4()),
                user_id=user_id,
                token_hash=hash_refresh_token(raw),
                family_id=family_id or str(uuid4()),
                expires_at=datetime.now(UTC) + timedelta(seconds=self.settings.refresh_token_ttl_seconds),
            )
        )
        return raw

    def _revoke_family(self, family_id: str, now: datetime) -> None:
        records = self.db.scalars(select(RefreshToken).where(RefreshToken.family_id == family_id)).all()
        for record in records:
            if record.revoked_at is None:
                record.revoked_at = now
        self.db.commit()
