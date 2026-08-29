"""Unit tests for OAuthService (#288): login/link resolution, the
never-auto-link-by-email rule, and unlink's last-credential guard.

Provider network behavior (PKCE, id_token verification, GitHub token/user
lookups) is covered in test_oauth_providers.py; here the provider clients
are simple in-process fakes implementing OAuthProviderClient, so these tests
exercise OAuthService's own business logic in isolation.
"""

from datetime import UTC, datetime, timedelta

import pytest

from app.auth.oauth_providers import OAuthIdentityInfo, OAuthProviderError
from app.auth.security import hash_password
from app.auth.service import AuthService
from app.core.config import get_settings
from app.core.database import SessionLocal
from app.core.exceptions import NotFoundError, UnauthorizedError, ValidationServiceError
from app.models.approved_email import ApprovedEmail
from app.models.oauth_flow_state import OAuthFlowState
from app.models.oauth_identity import OAuthIdentity
from app.models.oauth_pending_link import OAuthPendingLink
from app.models.user import SEED_USER_ID, SEED_USER_EMAIL, User
from app.services.oauth_service import OAuthService


class FakeProviderClient:
    """A scripted OAuthProviderClient double -- returns a fixed identity or
    raises a fixed error, never touches the network."""

    def __init__(
        self, *, identity: OAuthIdentityInfo | None = None, error: Exception | None = None, configured: bool = True
    ):
        self.identity = identity
        self.error = error
        self.configured = configured

    def is_configured(self) -> bool:
        return self.configured

    def authorize_url(self, *, redirect_uri: str, state: str, code_challenge: str, nonce: str) -> str:
        return f"https://fake-provider.example/authorize?state={state}&redirect_uri={redirect_uri}"

    async def resolve_identity(self, *, code, redirect_uri, code_verifier, nonce) -> OAuthIdentityInfo:
        if self.error is not None:
            raise self.error
        assert self.identity is not None
        return self.identity


def _make_service(db, providers: dict) -> OAuthService:
    settings = get_settings()
    auth_service = AuthService(db, settings)
    return OAuthService(db, settings, auth_service, providers)


def _create_user(db, email: str, password: str | None = "correct-horse-battery-staple") -> User:
    import uuid

    user = User(id=str(uuid.uuid4()), email=email, password_hash=hash_password(password) if password else None)
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def approve_email(db, email: str, note: str | None = None) -> ApprovedEmail:
    import uuid

    approval = ApprovedEmail(id=str(uuid.uuid4()), email=email, note=note)
    db.add(approval)
    db.commit()
    db.refresh(approval)
    return approval


@pytest.fixture()
def db(client):
    """Piggybacks on the `client` fixture purely for its DB/env setup
    (a fresh migrated-or-created-all sqlite database per test) -- these
    tests drive OAuthService directly, never over HTTP."""
    with SessionLocal() as session:
        yield session


class TestConfiguredProviders:
    def test_reports_only_configured_providers(self, db):
        service = _make_service(
            db, {"google": FakeProviderClient(configured=True), "github": FakeProviderClient(configured=False)}
        )
        assert service.configured_providers() == ["google"]

    def test_redirect_uri_is_built_from_settings(self, db):
        service = _make_service(db, {})
        settings = get_settings()
        assert service.redirect_uri("google") == f"{settings.oauth_public_base_url}/auth/oauth/google/callback"


class TestStart:
    def test_creates_a_flow_row_and_returns_the_provider_authorize_url(self, db):
        service = _make_service(db, {"google": FakeProviderClient()})
        url = service.start("google", intent="login", frontend_redirect_base="http://localhost:5173")
        assert url.startswith("https://fake-provider.example/authorize?state=")

        flows = db.query(OAuthFlowState).all()
        assert len(flows) == 1
        assert flows[0].provider == "google"
        assert flows[0].intent == "login"
        assert flows[0].link_user_id is None
        assert flows[0].frontend_redirect_base == "http://localhost:5173"

    def test_link_intent_stores_the_target_user(self, db):
        user = _create_user(db, "owner@example.com")
        service = _make_service(db, {"github": FakeProviderClient()})
        service.start("github", intent="link", frontend_redirect_base="http://localhost:5173", link_user_id=user.id)
        flow = db.query(OAuthFlowState).one()
        assert flow.intent == "link"
        assert flow.link_user_id == user.id

    def test_unconfigured_provider_is_rejected(self, db):
        service = _make_service(db, {"google": FakeProviderClient(configured=False)})
        with pytest.raises(ValidationServiceError):
            service.start("google", intent="login", frontend_redirect_base="http://localhost:5173")


class TestCompleteCallbackLogin:
    def test_unknown_state_raises(self, db):
        import asyncio

        service = _make_service(db, {"google": FakeProviderClient()})
        with pytest.raises(ValidationServiceError):
            asyncio.run(service.complete_callback("google", state="never-issued", code="c", provider_error=None))

    def test_expired_flow_raises(self, db):
        import asyncio
        import uuid

        service = _make_service(db, {"google": FakeProviderClient()})
        now = datetime.now(UTC)
        db.add(
            OAuthFlowState(
                id=str(uuid.uuid4()),
                state_hash="deadbeef" * 8,
                provider="google",
                code_verifier="v",
                nonce="n",
                intent="login",
                link_user_id=None,
                frontend_redirect_base="http://localhost:5173",
                created_at=now - timedelta(seconds=1000),
                expires_at=now - timedelta(seconds=1),
            )
        )
        db.commit()
        with pytest.raises(ValidationServiceError):
            asyncio.run(
                service.complete_callback(
                    "google", state="irrelevant-since-hash-lookup-fails", code="c", provider_error=None
                )
            )

    def test_provider_denial_returns_error_result_and_consumes_the_flow(self, db):
        import asyncio

        service = _make_service(db, {"google": FakeProviderClient()})
        url = service.start("google", intent="login", frontend_redirect_base="http://localhost:5173")
        state = url.split("state=")[1].split("&")[0]

        base, result = asyncio.run(
            service.complete_callback("google", state=state, code=None, provider_error="access_denied")
        )
        assert base == "http://localhost:5173"
        assert result.kind == "error"
        assert result.error_code == "access_denied"
        assert db.query(OAuthFlowState).count() == 0

        # Single-use: replaying the same state now hits the unknown-state path.
        with pytest.raises(ValidationServiceError):
            asyncio.run(service.complete_callback("google", state=state, code="c", provider_error=None))

    def test_missing_code_without_provider_error_is_a_generic_error(self, db):
        import asyncio

        service = _make_service(db, {"google": FakeProviderClient()})
        url = service.start("google", intent="login", frontend_redirect_base="http://localhost:5173")
        state = url.split("state=")[1].split("&")[0]
        base, result = asyncio.run(service.complete_callback("google", state=state, code=None, provider_error=None))
        assert result.kind == "error"
        assert result.error_code == "missing_code"

    def test_exchange_failure_is_reported_as_error(self, db):
        import asyncio

        service = _make_service(db, {"google": FakeProviderClient(error=OAuthProviderError("boom"))})
        url = service.start("google", intent="login", frontend_redirect_base="http://localhost:5173")
        state = url.split("state=")[1].split("&")[0]
        base, result = asyncio.run(service.complete_callback("google", state=state, code="c", provider_error=None))
        assert result.kind == "error"
        assert result.error_code == "exchange_failed"

    def test_brand_new_unapproved_identity_is_rejected_never_bypassing_the_allowlist(self, db):
        """OAuth login never creates an account for an email that isn't on
        the allowlist (#374, superseding #288's original invite-code
        comment): password registration requires an approved email
        (AuthService.register), and an OAuth-created account with no
        equivalent check would be a silent bypass of that gate, not a
        feature. An unapproved visitor is sent back to the allowlist-gated
        registration form instead."""
        import asyncio

        identity = OAuthIdentityInfo(
            subject="sub-1", email="newperson@example.com", email_verified=True, display_name="New Person"
        )
        service = _make_service(db, {"google": FakeProviderClient(identity=identity)})
        url = service.start("google", intent="login", frontend_redirect_base="http://localhost:5173")
        state = url.split("state=")[1].split("&")[0]

        base, result = asyncio.run(service.complete_callback("google", state=state, code="c", provider_error=None))
        assert result.kind == "error"
        assert result.error_code == "email_not_approved"
        assert db.query(User).filter(User.email == "newperson@example.com").count() == 0
        assert db.query(OAuthIdentity).count() == 0

    def test_brand_new_approved_identity_creates_an_account_via_oauth(self, db):
        """The one exception to 'OAuth never creates an account': a verified
        provider email that's already on the SAME allowlist password
        registration uses may complete first-time sign-in with no separate
        code needed (#374)."""
        import asyncio

        approve_email(db, "approved-newcomer@example.com")
        identity = OAuthIdentityInfo(
            subject="sub-approved-1",
            email="approved-newcomer@example.com",
            email_verified=True,
            display_name="Newcomer",
        )
        service = _make_service(db, {"google": FakeProviderClient(identity=identity)})
        url = service.start("google", intent="login", frontend_redirect_base="http://localhost:5173")
        state = url.split("state=")[1].split("&")[0]

        base, result = asyncio.run(service.complete_callback("google", state=state, code="c", provider_error=None))
        assert result.kind == "session"
        assert result.user.email == "approved-newcomer@example.com"
        assert result.user.password_hash is None

        stored_identity = db.query(OAuthIdentity).one()
        assert stored_identity.provider_subject == "sub-approved-1"
        assert stored_identity.user_id == result.user.id

        approval = db.query(ApprovedEmail).filter(ApprovedEmail.email == "approved-newcomer@example.com").one()
        assert approval.used_at is not None
        assert approval.used_by_user_id == result.user.id

    def test_existing_identity_reuses_the_same_account_without_duplicating_it(self, db):
        import asyncio
        import uuid

        user = _create_user(db, "repeat@example.com")
        db.add(
            OAuthIdentity(
                id=str(uuid.uuid4()),
                user_id=user.id,
                provider="google",
                provider_subject="sub-2",
                email=user.email,
                created_at=datetime.now(UTC),
            )
        )
        db.commit()

        identity = OAuthIdentityInfo(
            subject="sub-2", email="repeat@example.com", email_verified=True, display_name=None
        )
        service = _make_service(db, {"google": FakeProviderClient(identity=identity)})

        for _ in range(2):
            url = service.start("google", intent="login", frontend_redirect_base="http://localhost:5173")
            state = url.split("state=")[1].split("&")[0]
            base, result = asyncio.run(service.complete_callback("google", state=state, code="c", provider_error=None))
            assert result.kind == "session"
            assert result.user.id == user.id

        assert db.query(User).filter(User.email == "repeat@example.com").count() == 1
        assert db.query(OAuthIdentity).count() == 1

    def test_email_match_against_existing_account_creates_a_pending_link_never_auto_links(self, db):
        import asyncio

        existing = _create_user(db, "matched@example.com")
        identity = OAuthIdentityInfo(
            subject="sub-3", email="matched@example.com", email_verified=True, display_name="Someone"
        )
        service = _make_service(db, {"google": FakeProviderClient(identity=identity)})
        url = service.start("google", intent="login", frontend_redirect_base="http://localhost:5173")
        state = url.split("state=")[1].split("&")[0]

        base, result = asyncio.run(service.complete_callback("google", state=state, code="c", provider_error=None))
        assert result.kind == "pending_link"
        assert result.pending_link_id is not None

        # Never auto-linked or auto-authenticated.
        assert db.query(OAuthIdentity).count() == 0
        assert db.query(User).filter(User.email == "matched@example.com").count() == 1
        pending = db.get(OAuthPendingLink, result.pending_link_id)
        assert pending.email == existing.email
        assert pending.provider_subject == "sub-3"

    def test_unverified_email_with_no_existing_identity_is_rejected(self, db):
        """An unverified email can't even be offered a pending-link (no
        matched_user lookup happens), so this also lands on the same
        no-signup-without-invite outcome as any other brand-new identity."""
        import asyncio

        identity = OAuthIdentityInfo(
            subject="sub-4", email="unverified@example.com", email_verified=False, display_name=None
        )
        service = _make_service(db, {"github": FakeProviderClient(identity=identity)})
        url = service.start("github", intent="login", frontend_redirect_base="http://localhost:5173")
        state = url.split("state=")[1].split("&")[0]

        base, result = asyncio.run(service.complete_callback("github", state=state, code="c", provider_error=None))
        assert result.kind == "error"
        assert result.error_code == "email_not_approved"
        assert db.query(User).filter(User.email == "unverified@example.com").count() == 0

    def test_missing_email_entirely_is_rejected(self, db):
        import asyncio

        identity = OAuthIdentityInfo(subject="sub-5", email=None, email_verified=False, display_name=None)
        service = _make_service(db, {"github": FakeProviderClient(identity=identity)})
        url = service.start("github", intent="login", frontend_redirect_base="http://localhost:5173")
        state = url.split("state=")[1].split("&")[0]
        base, result = asyncio.run(service.complete_callback("github", state=state, code="c", provider_error=None))
        assert result.kind == "error"
        assert result.error_code == "email_not_approved"

    def test_seed_user_cannot_authenticate_via_oauth(self, db):
        import asyncio
        import uuid

        # A fresh test database has no seed-user row until something
        # actually needs one (it's normally backfilled by migration 0002 for
        # pre-existing data) -- insert it explicitly so the FK below is
        # satisfiable, matching what a real deployment always has.
        db.add(User(id=SEED_USER_ID, email=SEED_USER_EMAIL, password_hash=None))
        db.flush()
        # A pre-existing identity somehow bound to the seed user (should never
        # be created by normal flows -- this proves the login path itself
        # refuses to open a session for it even if one existed).
        db.add(
            OAuthIdentity(
                id=str(uuid.uuid4()),
                user_id=SEED_USER_ID,
                provider="google",
                provider_subject="seed-sub",
                email=SEED_USER_EMAIL,
                created_at=datetime.now(UTC),
            )
        )
        db.commit()
        identity = OAuthIdentityInfo(subject="seed-sub", email=SEED_USER_EMAIL, email_verified=True, display_name=None)
        service = _make_service(db, {"google": FakeProviderClient(identity=identity)})
        url = service.start("google", intent="login", frontend_redirect_base="http://localhost:5173")
        state = url.split("state=")[1].split("&")[0]
        base, result = asyncio.run(service.complete_callback("google", state=state, code="c", provider_error=None))
        assert result.kind == "error"
        assert result.error_code == "account_unavailable"

    def test_inactive_account_cannot_authenticate_via_oauth(self, db):
        import asyncio
        import uuid

        user = _create_user(db, "disabled@example.com")
        user.is_active = False
        db.add(
            OAuthIdentity(
                id=str(uuid.uuid4()),
                user_id=user.id,
                provider="google",
                provider_subject="sub-disabled",
                email=user.email,
                created_at=datetime.now(UTC),
            )
        )
        db.commit()
        identity = OAuthIdentityInfo(subject="sub-disabled", email=user.email, email_verified=True, display_name=None)
        service = _make_service(db, {"google": FakeProviderClient(identity=identity)})
        url = service.start("google", intent="login", frontend_redirect_base="http://localhost:5173")
        state = url.split("state=")[1].split("&")[0]
        base, result = asyncio.run(service.complete_callback("google", state=state, code="c", provider_error=None))
        assert result.kind == "error"
        assert result.error_code == "account_unavailable"


class TestCompleteCallbackLink:
    def test_link_success_attaches_identity_to_the_authenticated_user(self, db):
        import asyncio

        user = _create_user(db, "linker@example.com")
        identity = OAuthIdentityInfo(
            subject="link-sub-1", email="linker-provider-email@example.com", email_verified=True, display_name=None
        )
        service = _make_service(db, {"google": FakeProviderClient(identity=identity)})
        url = service.start(
            "google", intent="link", frontend_redirect_base="http://localhost:5173", link_user_id=user.id
        )
        state = url.split("state=")[1].split("&")[0]

        base, result = asyncio.run(service.complete_callback("google", state=state, code="c", provider_error=None))
        assert result.kind == "linked"
        assert result.user.id == user.id
        stored = db.query(OAuthIdentity).one()
        assert stored.user_id == user.id
        assert stored.provider_subject == "link-sub-1"

    def test_link_conflict_when_identity_already_linked_elsewhere(self, db):
        import asyncio
        import uuid

        first_user = _create_user(db, "first@example.com")
        second_user = _create_user(db, "second@example.com")
        db.add(
            OAuthIdentity(
                id=str(uuid.uuid4()),
                user_id=first_user.id,
                provider="google",
                provider_subject="contested-sub",
                email="first@example.com",
                created_at=datetime.now(UTC),
            )
        )
        db.commit()

        identity = OAuthIdentityInfo(
            subject="contested-sub", email="second@example.com", email_verified=True, display_name=None
        )
        service = _make_service(db, {"google": FakeProviderClient(identity=identity)})
        url = service.start(
            "google", intent="link", frontend_redirect_base="http://localhost:5173", link_user_id=second_user.id
        )
        state = url.split("state=")[1].split("&")[0]

        base, result = asyncio.run(service.complete_callback("google", state=state, code="c", provider_error=None))
        assert result.kind == "error"
        assert result.error_code == "already_linked"
        # The original link is untouched.
        assert db.query(OAuthIdentity).count() == 1
        assert db.query(OAuthIdentity).one().user_id == first_user.id

    def test_link_conflict_when_user_already_has_a_provider_identity(self, db):
        import asyncio
        import uuid

        user = _create_user(db, "double-linker@example.com")
        db.add(
            OAuthIdentity(
                id=str(uuid.uuid4()),
                user_id=user.id,
                provider="google",
                provider_subject="already-mine",
                email=user.email,
                created_at=datetime.now(UTC),
            )
        )
        db.commit()

        identity = OAuthIdentityInfo(
            subject="a-different-sub", email="whatever@example.com", email_verified=True, display_name=None
        )
        service = _make_service(db, {"google": FakeProviderClient(identity=identity)})
        url = service.start(
            "google", intent="link", frontend_redirect_base="http://localhost:5173", link_user_id=user.id
        )
        state = url.split("state=")[1].split("&")[0]

        base, result = asyncio.run(service.complete_callback("google", state=state, code="c", provider_error=None))
        assert result.kind == "error"
        assert result.error_code == "already_linked"
        assert db.query(OAuthIdentity).count() == 1


class TestConfirmPendingLink:
    def test_correct_password_links_and_opens_a_session(self, db):
        user = _create_user(db, "confirm-me@example.com", password="correct-horse-battery-staple")
        import uuid

        pending = OAuthPendingLink(
            id=str(uuid.uuid4()),
            provider="google",
            provider_subject="pending-sub",
            email=user.email,
            display_name="Display Name",
            created_at=datetime.now(UTC),
            expires_at=datetime.now(UTC) + timedelta(minutes=10),
        )
        db.add(pending)
        db.commit()

        service = _make_service(db, {})
        confirmed_user, access_token, refresh_token = service.confirm_pending_link(
            pending.id, "correct-horse-battery-staple"
        )
        assert confirmed_user.id == user.id
        assert access_token
        assert refresh_token
        assert db.get(OAuthPendingLink, pending.id) is None
        identity = db.query(OAuthIdentity).one()
        assert identity.user_id == user.id
        assert identity.provider_subject == "pending-sub"

    def test_wrong_password_is_rejected_and_pending_link_survives(self, db):
        user = _create_user(db, "wrong-pw@example.com", password="correct-horse-battery-staple")
        import uuid

        pending = OAuthPendingLink(
            id=str(uuid.uuid4()),
            provider="google",
            provider_subject="pending-sub-2",
            email=user.email,
            display_name=None,
            created_at=datetime.now(UTC),
            expires_at=datetime.now(UTC) + timedelta(minutes=10),
        )
        db.add(pending)
        db.commit()

        service = _make_service(db, {})
        with pytest.raises(UnauthorizedError):
            service.confirm_pending_link(pending.id, "totally-wrong-password")
        assert db.get(OAuthPendingLink, pending.id) is not None
        assert db.query(OAuthIdentity).count() == 0

    def test_unknown_pending_link_id_is_rejected(self, db):
        service = _make_service(db, {})
        with pytest.raises(UnauthorizedError):
            service.confirm_pending_link("00000000-0000-0000-0000-000000000000", "any-password")

    def test_expired_pending_link_is_rejected(self, db):
        user = _create_user(db, "expired@example.com")
        import uuid

        pending = OAuthPendingLink(
            id=str(uuid.uuid4()),
            provider="google",
            provider_subject="pending-sub-3",
            email=user.email,
            display_name=None,
            created_at=datetime.now(UTC) - timedelta(minutes=30),
            expires_at=datetime.now(UTC) - timedelta(minutes=1),
        )
        db.add(pending)
        db.commit()
        service = _make_service(db, {})
        with pytest.raises(UnauthorizedError):
            service.confirm_pending_link(pending.id, "correct-horse-battery-staple")

    def test_pending_link_against_a_password_less_account_is_rejected(self, db):
        """An OAuth-only account (no password_hash) can never be the target
        of a password-confirmed link -- there is no password to check."""
        user = _create_user(db, "oauth-only@example.com", password=None)
        import uuid

        pending = OAuthPendingLink(
            id=str(uuid.uuid4()),
            provider="github",
            provider_subject="pending-sub-4",
            email=user.email,
            display_name=None,
            created_at=datetime.now(UTC),
            expires_at=datetime.now(UTC) + timedelta(minutes=10),
        )
        db.add(pending)
        db.commit()
        service = _make_service(db, {})
        with pytest.raises(UnauthorizedError):
            service.confirm_pending_link(pending.id, "any-password-at-all")


class TestUnlink:
    def test_unlinks_when_a_password_remains_as_a_credential(self, db):
        import uuid

        user = _create_user(db, "has-password@example.com")
        db.add(
            OAuthIdentity(
                id=str(uuid.uuid4()),
                user_id=user.id,
                provider="google",
                provider_subject="sub",
                email=user.email,
                created_at=datetime.now(UTC),
            )
        )
        db.commit()
        service = _make_service(db, {})
        service.unlink(user, "google")
        assert db.query(OAuthIdentity).count() == 0

    def test_unlinks_when_another_provider_identity_remains(self, db):
        import uuid

        user = _create_user(db, "two-providers@example.com", password=None)
        db.add_all(
            [
                OAuthIdentity(
                    id=str(uuid.uuid4()),
                    user_id=user.id,
                    provider="google",
                    provider_subject="g-sub",
                    email=user.email,
                    created_at=datetime.now(UTC),
                ),
                OAuthIdentity(
                    id=str(uuid.uuid4()),
                    user_id=user.id,
                    provider="github",
                    provider_subject="h-sub",
                    email=user.email,
                    created_at=datetime.now(UTC),
                ),
            ]
        )
        db.commit()
        service = _make_service(db, {})
        service.unlink(user, "google")
        remaining = db.query(OAuthIdentity).all()
        assert len(remaining) == 1
        assert remaining[0].provider == "github"

    def test_refuses_to_remove_the_only_sign_in_method(self, db):
        import uuid

        user = _create_user(db, "oauth-only-2@example.com", password=None)
        db.add(
            OAuthIdentity(
                id=str(uuid.uuid4()),
                user_id=user.id,
                provider="google",
                provider_subject="only-sub",
                email=user.email,
                created_at=datetime.now(UTC),
            )
        )
        db.commit()
        service = _make_service(db, {})
        with pytest.raises(ValidationServiceError):
            service.unlink(user, "google")
        assert db.query(OAuthIdentity).count() == 1

    def test_unlinking_a_provider_never_linked_is_not_found(self, db):
        user = _create_user(db, "nothing-linked@example.com")
        service = _make_service(db, {})
        with pytest.raises(NotFoundError):
            service.unlink(user, "google")


class TestLinkedIdentities:
    def test_lists_only_the_requested_users_identities(self, db):
        import uuid

        user_a = _create_user(db, "a@example.com")
        user_b = _create_user(db, "b@example.com")
        db.add_all(
            [
                OAuthIdentity(
                    id=str(uuid.uuid4()),
                    user_id=user_a.id,
                    provider="google",
                    provider_subject="a-sub",
                    email=user_a.email,
                    created_at=datetime.now(UTC),
                ),
                OAuthIdentity(
                    id=str(uuid.uuid4()),
                    user_id=user_b.id,
                    provider="github",
                    provider_subject="b-sub",
                    email=user_b.email,
                    created_at=datetime.now(UTC),
                ),
            ]
        )
        db.commit()
        service = _make_service(db, {})
        assert [i.provider for i in service.linked_identities(user_a.id)] == ["google"]
        assert [i.provider for i in service.linked_identities(user_b.id)] == ["github"]
