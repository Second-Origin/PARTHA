"""OAuth sign-in and account-linking business logic (#288).

Credentials-deferred build: fully implemented and covered by tests using
clearly-fake mocked provider clients (app/auth/oauth_providers.py). See the
comment on issue #288 for exactly what still needs the owner's real client
id/secret and a decided public callback domain before this can go live.

Linking rule enforced throughout: a matching email is never sufficient on
its own to sign into or link an existing account. A newly-discovered
identity whose verified email matches an existing account produces an
OAuthPendingLink and requires that account's password before the two are
connected (confirm_pending_link) -- there is no silent-merge path.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Literal
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.auth.oauth_providers import (
    OAuthIdentityInfo,
    OAuthProviderClient,
    OAuthProviderError,
    generate_nonce,
    generate_pkce_pair,
    generate_state,
)
from app.auth.security import burn_password_check, hash_refresh_token, verify_password
from app.auth.service import AuthService
from app.core.config import Settings
from app.core.exceptions import ConflictServiceError, NotFoundError, UnauthorizedError, ValidationServiceError
from app.models.oauth_flow_state import OAuthFlowState
from app.models.oauth_identity import OAuthIdentity
from app.models.oauth_pending_link import OAuthPendingLink
from app.models.user import SEED_USER_ID, User

logger = logging.getLogger(__name__)

# A real callback happens within seconds of the redirect; these bound how
# long an abandoned flow/pending-link lingers before it's simply unusable.
FLOW_TTL_SECONDS = 600
PENDING_LINK_TTL_SECONDS = 600

INVALID_OAUTH_STATE = "This sign-in link has expired or was already used. Please try again."
PROVIDER_UNAVAILABLE = "This sign-in method isn't available right now."


def _as_utc(value: datetime) -> datetime:
    # Same normalization as app.auth.service: SQLite hands back naive
    # datetimes for DateTime(timezone=True) columns, Postgres hands back
    # aware ones.
    return value if value.tzinfo is not None else value.replace(tzinfo=UTC)


def _hash_state(raw: str) -> str:
    # Same sha256-hex construction as refresh tokens/invite codes: `state` is
    # a bearer secret (the CSRF protection), so only its hash is stored.
    return hash_refresh_token(raw)


@dataclass(frozen=True)
class OAuthLoginResult:
    kind: Literal["session", "linked", "pending_link", "error"]
    user: User | None = None
    access_token: str | None = None
    refresh_token: str | None = None
    pending_link_id: str | None = None
    error_code: str | None = None


class OAuthService:
    def __init__(
        self,
        db: Session,
        settings: Settings,
        auth_service: AuthService,
        providers: dict[str, OAuthProviderClient],
    ) -> None:
        self.db = db
        self.settings = settings
        self.auth_service = auth_service
        self.providers = providers

    def configured_providers(self) -> list[str]:
        return [name for name, client in self.providers.items() if client.is_configured()]

    def redirect_uri(self, provider: str) -> str:
        # Fixed per (deployment, provider) -- exactly what must be registered
        # with the provider's console -- so it is derived, never stored per
        # flow; the /start and callback routes always agree by construction.
        return f"{self.settings.oauth_public_base_url.rstrip('/')}/auth/oauth/{provider}/callback"

    def _require_client(self, provider: str) -> OAuthProviderClient:
        client = self.providers.get(provider)
        if client is None or not client.is_configured():
            raise ValidationServiceError(PROVIDER_UNAVAILABLE)
        return client

    def start(
        self,
        provider: str,
        *,
        intent: Literal["login", "link"],
        frontend_redirect_base: str,
        link_user_id: str | None = None,
    ) -> str:
        client = self._require_client(provider)
        state = generate_state()
        code_verifier, code_challenge = generate_pkce_pair()
        nonce = generate_nonce()
        now = datetime.now(UTC)
        self.db.add(
            OAuthFlowState(
                id=str(uuid4()),
                state_hash=_hash_state(state),
                provider=provider,
                code_verifier=code_verifier,
                nonce=nonce,
                intent=intent,
                link_user_id=link_user_id,
                frontend_redirect_base=frontend_redirect_base,
                created_at=now,
                expires_at=now + timedelta(seconds=FLOW_TTL_SECONDS),
            )
        )
        self.db.commit()
        return client.authorize_url(
            redirect_uri=self.redirect_uri(provider), state=state, code_challenge=code_challenge, nonce=nonce
        )

    async def complete_callback(
        self, provider: str, *, state: str, code: str | None, provider_error: str | None
    ) -> tuple[str, OAuthLoginResult]:
        """Consume a single-use flow state and resolve it to an outcome.

        The flow row is deleted the moment it's read, success or failure, so
        a replayed callback can never reuse a state value. Raises only for a
        state this server never issued (or already consumed) -- every other
        failure (provider denial, exchange failure, unverified email, an
        email collision) comes back as an ``OAuthLoginResult(kind="error")``
        so the caller can still redirect the browser back to the frontend
        that started the flow.
        """
        flow = self.db.scalars(select(OAuthFlowState).where(OAuthFlowState.state_hash == _hash_state(state))).first()
        if flow is None or _as_utc(flow.expires_at) <= datetime.now(UTC):
            raise ValidationServiceError(INVALID_OAUTH_STATE)

        frontend_redirect_base = flow.frontend_redirect_base
        flow_intent = flow.intent
        flow_link_user_id = flow.link_user_id
        code_verifier = flow.code_verifier
        nonce = flow.nonce
        self.db.delete(flow)
        self.db.commit()

        if provider_error is not None:
            logger.info("OAuth flow denied or cancelled", extra={"provider": provider, "reason": provider_error})
            return frontend_redirect_base, OAuthLoginResult(kind="error", error_code=provider_error)
        if not code:
            return frontend_redirect_base, OAuthLoginResult(kind="error", error_code="missing_code")

        try:
            client = self._require_client(provider)
        except ValidationServiceError:
            return frontend_redirect_base, OAuthLoginResult(kind="error", error_code="provider_unavailable")

        try:
            identity = await client.resolve_identity(
                code=code, redirect_uri=self.redirect_uri(provider), code_verifier=code_verifier, nonce=nonce
            )
        except OAuthProviderError:
            logger.warning("OAuth provider exchange failed", exc_info=True, extra={"provider": provider})
            return frontend_redirect_base, OAuthLoginResult(kind="error", error_code="exchange_failed")

        if flow_intent == "link":
            result = self._complete_link(provider, identity, flow_link_user_id)
        else:
            result = self._complete_login(provider, identity)
        return frontend_redirect_base, result

    def _complete_login(self, provider: str, identity: OAuthIdentityInfo) -> OAuthLoginResult:
        existing = self.db.scalars(
            select(OAuthIdentity).where(
                OAuthIdentity.provider == provider, OAuthIdentity.provider_subject == identity.subject
            )
        ).first()
        if existing is not None:
            user = self.db.get(User, existing.user_id)
            if user is None or not user.is_active or user.id == SEED_USER_ID:
                return OAuthLoginResult(kind="error", error_code="account_unavailable")
            db_user, access_token, refresh_token = self.auth_service.open_session(user)
            return OAuthLoginResult(
                kind="session", user=db_user, access_token=access_token, refresh_token=refresh_token
            )

        # No linked identity yet. An email match against an existing account
        # is never sufficient on its own to sign into it -- only to offer a
        # password-confirmed link, and only when the provider itself has
        # verified that email (an unverified email is not proof of anything).
        if identity.email and identity.email_verified:
            matched_user = self.db.scalars(select(User).where(User.email == identity.email.strip().lower())).first()
            if matched_user is not None and matched_user.id != SEED_USER_ID:
                now = datetime.now(UTC)
                pending = OAuthPendingLink(
                    id=str(uuid4()),
                    provider=provider,
                    provider_subject=identity.subject,
                    email=matched_user.email,
                    display_name=identity.display_name,
                    created_at=now,
                    expires_at=now + timedelta(seconds=PENDING_LINK_TTL_SECONDS),
                )
                self.db.add(pending)
                self.db.commit()
                return OAuthLoginResult(kind="pending_link", pending_link_id=pending.id)

        # No existing account to sign into or link -- and, deliberately, no
        # brand-new account is created here either. Registration is
        # invite-gated everywhere else in the product (AuthService.register
        # requires a redeemed invite code); silently creating an account over
        # OAuth with no invite check at all would be a real, unintended
        # bypass of that gate, not a feature. Until there's a real decision
        # on how an invite code fits into the OAuth flow, a new visitor is
        # sent back to the invite-gated registration form instead.
        return OAuthLoginResult(kind="error", error_code="signup_requires_invite")

    def _complete_link(self, provider: str, identity: OAuthIdentityInfo, link_user_id: str | None) -> OAuthLoginResult:
        if not link_user_id:
            return OAuthLoginResult(kind="error", error_code="missing_link_target")
        user = self.db.get(User, link_user_id)
        if user is None or not user.is_active:
            return OAuthLoginResult(kind="error", error_code="account_unavailable")
        self.db.add(
            OAuthIdentity(
                id=str(uuid4()),
                user_id=user.id,
                provider=provider,
                provider_subject=identity.subject,
                email=identity.email,
                created_at=datetime.now(UTC),
            )
        )
        try:
            self.db.commit()
        except IntegrityError:
            # Either this external identity is already linked to a different
            # PARTHA account, or this account already has a provider
            # identity linked -- both are the unique constraints on
            # OAuthIdentity, not distinguished further here.
            self.db.rollback()
            return OAuthLoginResult(kind="error", error_code="already_linked")
        return OAuthLoginResult(kind="linked", user=user)

    def confirm_pending_link(self, pending_link_id: str, password: str) -> tuple[User, str, str]:
        now = datetime.now(UTC)
        pending = self.db.get(OAuthPendingLink, pending_link_id)
        if pending is None or _as_utc(pending.expires_at) <= now:
            burn_password_check(password)
            raise UnauthorizedError(INVALID_OAUTH_STATE)

        user = self.db.scalars(select(User).where(User.email == pending.email)).first()
        if user is None or user.password_hash is None:
            burn_password_check(password)
            raise UnauthorizedError(INVALID_OAUTH_STATE)
        if not verify_password(user.password_hash, password) or not user.is_active:
            raise UnauthorizedError(INVALID_OAUTH_STATE)

        self.db.add(
            OAuthIdentity(
                id=str(uuid4()),
                user_id=user.id,
                provider=pending.provider,
                provider_subject=pending.provider_subject,
                email=pending.email,
                created_at=now,
            )
        )
        self.db.delete(pending)
        try:
            self.db.commit()
        except IntegrityError:
            self.db.rollback()
            raise ConflictServiceError("This provider account is already linked to a different account.") from None
        return self.auth_service.open_session(user)

    def linked_identities(self, user_id: str) -> list[OAuthIdentity]:
        return list(self.db.scalars(select(OAuthIdentity).where(OAuthIdentity.user_id == user_id)).all())

    def unlink(self, user: User, provider: str) -> None:
        identity = self.db.scalars(
            select(OAuthIdentity).where(OAuthIdentity.user_id == user.id, OAuthIdentity.provider == provider)
        ).first()
        if identity is None:
            raise NotFoundError(f"No linked {provider} account.", {"provider": provider})
        if user.password_hash is None:
            remaining = self.db.scalars(
                select(OAuthIdentity).where(OAuthIdentity.user_id == user.id, OAuthIdentity.provider != provider)
            ).first()
            if remaining is None:
                raise ValidationServiceError(
                    "This is your only way to sign in to this account. Link another provider before removing it."
                )
        self.db.delete(identity)
        self.db.commit()
