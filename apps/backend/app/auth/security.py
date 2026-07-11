import hashlib
import secrets
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import VerificationError, VerifyMismatchError

from app.core.config import Settings
from app.core.exceptions import UnauthorizedError

JWT_ALGORITHM = "HS256"

_hasher = PasswordHasher()

# Verified against when login hits an unknown email or a user without a
# credential, so those paths cost the same as a real password check and the
# response cannot be timed to enumerate accounts.
_DUMMY_HASH = _hasher.hash("partha-timing-equalizer")


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(password_hash: str, password: str) -> bool:
    try:
        return _hasher.verify(password_hash, password)
    except (VerifyMismatchError, VerificationError):
        return False


def burn_password_check(password: str) -> None:
    """Spend one argon2 verification without authenticating anyone."""
    try:
        _hasher.verify(_DUMMY_HASH, password)
    except (VerifyMismatchError, VerificationError):
        pass


def create_access_token(user_id: str, settings: Settings, ttl_seconds: int | None = None) -> str:
    now = datetime.now(UTC)
    ttl = settings.access_token_ttl_seconds if ttl_seconds is None else ttl_seconds
    claims = {
        "sub": user_id,
        "iat": now,
        "exp": now + timedelta(seconds=ttl),
        "jti": uuid4().hex,
    }
    return jwt.encode(claims, settings.auth_secret_key, algorithm=JWT_ALGORITHM)


def decode_access_token(token: str, settings: Settings) -> str:
    """Return the user id from a valid access token, or raise UnauthorizedError.

    Expired, malformed, and wrongly-signed tokens all surface the same generic
    message so a caller cannot distinguish why a token was rejected.
    """
    try:
        claims = jwt.decode(token, settings.auth_secret_key, algorithms=[JWT_ALGORITHM])
    except jwt.PyJWTError as exc:
        raise UnauthorizedError("Invalid or expired access token.") from exc
    user_id = claims.get("sub")
    if not isinstance(user_id, str) or not user_id:
        raise UnauthorizedError("Invalid or expired access token.")
    return user_id


def new_refresh_token() -> str:
    return secrets.token_urlsafe(48)


def hash_refresh_token(raw: str) -> str:
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()
