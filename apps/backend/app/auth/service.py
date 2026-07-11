import logging
from datetime import UTC, datetime, timedelta
from uuid import uuid4

from sqlalchemy import select
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
from app.core.exceptions import ConflictServiceError, UnauthorizedError
from app.models.refresh_token import RefreshToken
from app.models.user import User

logger = logging.getLogger(__name__)

# Every credential failure returns this exact message so responses cannot be
# used to tell apart unknown email / wrong password / disabled account.
INVALID_CREDENTIALS = "Invalid email or password."
INVALID_REFRESH = "Invalid refresh token."


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
        existing = self.db.scalars(select(User).where(User.email == normalized)).first()
        if existing:
            raise ConflictServiceError("An account with this email already exists.")

        user = User(id=str(uuid4()), email=normalized, password_hash=hash_password(password))
        self.db.add(user)
        self.db.commit()
        self.db.refresh(user)
        return self._open_session(user)

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
        return self._open_session(user)

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

        record.used_at = now
        raw_successor = self._issue_refresh(user.id, record.family_id)
        self.db.commit()
        return user, create_access_token(user.id, self.settings), raw_successor

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

    def _open_session(self, user: User) -> tuple[User, str, str]:
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
