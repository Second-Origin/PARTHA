"""HTTP-level integration tests for /auth/oauth/* (#288).

Provider clients are overridden via FastAPI's dependency_overrides with
in-process fakes (business logic is covered by test_oauth_service.py,
provider network behavior by test_oauth_providers.py) -- these tests exist
to prove the routing, cookie, redirect, and auth-dependency wiring itself:
that a real request through the real app reaches OAuthService and comes
back with the right status code, redirect target, and cookie.
"""

from urllib.parse import parse_qs, urlparse

from app.api.deps import get_github_oauth_client, get_google_oauth_client
from app.api.routes.auth import REFRESH_COOKIE
from app.auth.oauth_providers import OAuthIdentityInfo, OAuthProviderError
from tests.conftest import DEFAULT_TEST_PASSWORD, register_user


class FakeProviderClient:
    def __init__(self, *, identity=None, error=None, configured=True):
        self.identity = identity
        self.error = error
        self.configured = configured

    def is_configured(self):
        return self.configured

    def authorize_url(self, *, redirect_uri, state, code_challenge, nonce):
        return f"https://fake-provider.example/authorize?state={state}"

    async def resolve_identity(self, *, code, redirect_uri, code_verifier, nonce):
        if self.error is not None:
            raise self.error
        return self.identity


def _override(client, *, google=None, github=None):
    if google is not None:
        client.app.dependency_overrides[get_google_oauth_client] = lambda: google
    if github is not None:
        client.app.dependency_overrides[get_github_oauth_client] = lambda: github


def _clear_overrides(client):
    client.app.dependency_overrides.pop(get_google_oauth_client, None)
    client.app.dependency_overrides.pop(get_github_oauth_client, None)


def _state_from(authorize_url: str) -> str:
    return parse_qs(urlparse(authorize_url).query)["state"][0]


class TestProvidersEndpoint:
    def test_reports_none_configured_by_default(self, client):
        response = client.get("/auth/oauth/providers")
        assert response.status_code == 200
        assert response.json() == {"providers": []}

    def test_reports_configured_providers(self, client):
        _override(client, google=FakeProviderClient(configured=True), github=FakeProviderClient(configured=False))
        try:
            response = client.get("/auth/oauth/providers")
            assert response.json() == {"providers": ["google"]}
        finally:
            _clear_overrides(client)


class TestStartEndpoint:
    def test_unconfigured_provider_start_is_rejected(self, client):
        response = client.get("/auth/oauth/google/start")
        assert response.status_code == 422

    def test_unknown_provider_is_rejected(self, client):
        response = client.get("/auth/oauth/nope/start")
        assert response.status_code == 422

    def test_configured_provider_returns_an_authorize_url(self, client):
        _override(client, google=FakeProviderClient())
        try:
            response = client.get("/auth/oauth/google/start", headers={"Origin": "http://testserver"})
            assert response.status_code == 200
            assert response.json()["authorizeUrl"].startswith("https://fake-provider.example/authorize?state=")
        finally:
            _clear_overrides(client)

    def test_link_start_requires_authentication(self, client):
        _override(client, google=FakeProviderClient())
        try:
            response = client.post("/auth/oauth/google/link")
            assert response.status_code == 401
        finally:
            _clear_overrides(client)

    def test_authenticated_link_start_succeeds(self, auth_client):
        _override(auth_client, google=FakeProviderClient())
        try:
            response = auth_client.post("/auth/oauth/google/link", headers={"Origin": "http://testserver"})
            assert response.status_code == 200
            assert "authorizeUrl" in response.json()
        finally:
            _clear_overrides(auth_client)


class TestCallbackEndpoint:
    def test_missing_state_is_rejected(self, client):
        response = client.get("/auth/oauth/google/callback", params={"code": "c"}, follow_redirects=False)
        assert response.status_code == 422

    def test_unknown_state_is_rejected(self, client):
        response = client.get(
            "/auth/oauth/google/callback", params={"code": "c", "state": "never-issued"}, follow_redirects=False
        )
        assert response.status_code == 422

    def test_provider_denial_redirects_with_error(self, client):
        fake = FakeProviderClient()
        _override(client, google=fake)
        try:
            start = client.get("/auth/oauth/google/start", headers={"Origin": "http://testserver"})
            state = _state_from(start.json()["authorizeUrl"])
            response = client.get(
                "/auth/oauth/google/callback", params={"state": state, "error": "access_denied"}, follow_redirects=False
            )
            assert response.status_code == 302
            location = response.headers["location"]
            assert location.startswith("http://testserver/oauth/complete?status=error")
            assert "reason=access_denied" in location
        finally:
            _clear_overrides(client)

    def test_successful_login_for_an_already_linked_identity_sets_refresh_cookie(self, auth_client):
        """Login-over-OAuth only ever succeeds for an identity that's already
        linked to a real account (#288 comment: a brand-new account is never
        created over OAuth, since that would bypass the invite-code gate) --
        so this links first (as the authenticated user would from Settings),
        then proves an unauthenticated /start + /callback with that same
        identity is a real, cookie-issuing login."""
        from app.auth.oauth_providers import OAuthIdentityInfo as _Identity

        identity = _Identity(
            subject="linked-sub", email="linked-login@example.com", email_verified=True, display_name=None
        )
        _override(auth_client, google=FakeProviderClient(identity=identity))
        try:
            start = auth_client.post("/auth/oauth/google/link", headers={"Origin": "http://testserver"})
            state = _state_from(start.json()["authorizeUrl"])
            auth_client.get(
                "/auth/oauth/google/callback", params={"state": state, "code": "fake-code"}, follow_redirects=False
            )
        finally:
            _clear_overrides(auth_client)

        anonymous = type(auth_client)(auth_client.app)
        _override(anonymous, google=FakeProviderClient(identity=identity))
        try:
            start = anonymous.get("/auth/oauth/google/start", headers={"Origin": "http://testserver"})
            state = _state_from(start.json()["authorizeUrl"])
            response = anonymous.get(
                "/auth/oauth/google/callback", params={"state": state, "code": "fake-code"}, follow_redirects=False
            )
            assert response.status_code == 302
            assert response.headers["location"] == "http://testserver/oauth/complete?status=success"
            assert REFRESH_COOKIE in response.cookies

            # The refresh cookie actually works: bootstrap()'s primitive.
            refresh_response = anonymous.post("/auth/refresh")
            assert refresh_response.status_code == 200
            assert refresh_response.json()["user"]["id"] == auth_client.default_user["id"]
        finally:
            _clear_overrides(anonymous)

    def test_brand_new_identity_redirects_to_signup_required(self, client):
        identity = OAuthIdentityInfo(
            subject="never-seen-sub", email="brandnew@example.com", email_verified=True, display_name="Brand New"
        )
        fake = FakeProviderClient(identity=identity)
        _override(client, google=fake)
        try:
            start = client.get("/auth/oauth/google/start", headers={"Origin": "http://testserver"})
            state = _state_from(start.json()["authorizeUrl"])
            response = client.get(
                "/auth/oauth/google/callback", params={"state": state, "code": "fake-code"}, follow_redirects=False
            )
            assert response.status_code == 302
            location = response.headers["location"]
            assert "status=error" in location
            assert "reason=signup_requires_invite" in location
            assert REFRESH_COOKIE not in response.cookies
        finally:
            _clear_overrides(client)

    def test_exchange_failure_redirects_with_generic_error(self, client):
        fake = FakeProviderClient(error=OAuthProviderError("network exploded"))
        _override(client, google=fake)
        try:
            start = client.get("/auth/oauth/google/start", headers={"Origin": "http://testserver"})
            state = _state_from(start.json()["authorizeUrl"])
            response = client.get(
                "/auth/oauth/google/callback", params={"state": state, "code": "fake-code"}, follow_redirects=False
            )
            assert response.status_code == 302
            assert "status=error" in response.headers["location"]
            assert "reason=exchange_failed" in response.headers["location"]
        finally:
            _clear_overrides(client)

    def test_email_collision_redirects_to_pending_link(self, client):
        register_user(client, "collides@example.com")
        identity = OAuthIdentityInfo(
            subject="collide-sub", email="collides@example.com", email_verified=True, display_name=None
        )
        fake = FakeProviderClient(identity=identity)
        _override(client, google=fake)
        try:
            start = client.get("/auth/oauth/google/start", headers={"Origin": "http://testserver"})
            state = _state_from(start.json()["authorizeUrl"])
            response = client.get(
                "/auth/oauth/google/callback", params={"state": state, "code": "fake-code"}, follow_redirects=False
            )
            assert response.status_code == 302
            location = response.headers["location"]
            assert "status=pending-link" in location
            assert "pendingLinkId=" in location
            assert REFRESH_COOKIE not in response.cookies
        finally:
            _clear_overrides(client)

    def test_link_callback_attaches_identity_without_reauthenticating(self, auth_client):
        identity = OAuthIdentityInfo(
            subject="link-sub", email="whatever@example.com", email_verified=True, display_name=None
        )
        fake = FakeProviderClient(identity=identity)
        _override(auth_client, github=fake)
        try:
            start = auth_client.post("/auth/oauth/github/link", headers={"Origin": "http://testserver"})
            state = _state_from(start.json()["authorizeUrl"])
            response = auth_client.get(
                "/auth/oauth/github/callback", params={"state": state, "code": "fake-code"}, follow_redirects=False
            )
            assert response.status_code == 302
            assert "status=linked" in response.headers["location"]
            assert REFRESH_COOKIE not in response.cookies

            linked = auth_client.get("/auth/oauth/linked")
            assert linked.status_code == 200
            assert [entry["provider"] for entry in linked.json()["identities"]] == ["github"]
        finally:
            _clear_overrides(auth_client)


class TestLinkConfirmEndpoint:
    def test_confirms_with_correct_password_and_signs_in(self, client):
        register_user(client, "confirmable@example.com")
        identity = OAuthIdentityInfo(
            subject="confirm-sub", email="confirmable@example.com", email_verified=True, display_name=None
        )
        fake = FakeProviderClient(identity=identity)
        _override(client, google=fake)
        try:
            start = client.get("/auth/oauth/google/start", headers={"Origin": "http://testserver"})
            state = _state_from(start.json()["authorizeUrl"])
            callback = client.get(
                "/auth/oauth/google/callback", params={"state": state, "code": "fake-code"}, follow_redirects=False
            )
            pending_link_id = parse_qs(urlparse(callback.headers["location"]).query)["pendingLinkId"][0]

            response = client.post(
                "/auth/oauth/link/confirm", json={"pendingLinkId": pending_link_id, "password": DEFAULT_TEST_PASSWORD}
            )
            assert response.status_code == 200
            assert response.json()["user"]["email"] == "confirmable@example.com"
            assert REFRESH_COOKIE in response.cookies
        finally:
            _clear_overrides(client)

    def test_wrong_password_is_rejected(self, client):
        register_user(client, "confirmable2@example.com")
        identity = OAuthIdentityInfo(
            subject="confirm-sub-2", email="confirmable2@example.com", email_verified=True, display_name=None
        )
        fake = FakeProviderClient(identity=identity)
        _override(client, google=fake)
        try:
            start = client.get("/auth/oauth/google/start", headers={"Origin": "http://testserver"})
            state = _state_from(start.json()["authorizeUrl"])
            callback = client.get(
                "/auth/oauth/google/callback", params={"state": state, "code": "fake-code"}, follow_redirects=False
            )
            pending_link_id = parse_qs(urlparse(callback.headers["location"]).query)["pendingLinkId"][0]

            response = client.post(
                "/auth/oauth/link/confirm",
                json={"pendingLinkId": pending_link_id, "password": "wrong-password-entirely"},
            )
            assert response.status_code == 401
        finally:
            _clear_overrides(client)


class TestUnlinkEndpoint:
    def test_unlink_requires_authentication(self, client):
        response = client.delete("/auth/oauth/google")
        assert response.status_code == 401

    def test_unlink_removes_a_linked_identity(self, auth_client):
        identity = OAuthIdentityInfo(
            subject="unlink-sub", email="whatever2@example.com", email_verified=True, display_name=None
        )
        fake = FakeProviderClient(identity=identity)
        _override(auth_client, github=fake)
        try:
            start = auth_client.post("/auth/oauth/github/link", headers={"Origin": "http://testserver"})
            state = _state_from(start.json()["authorizeUrl"])
            auth_client.get(
                "/auth/oauth/github/callback", params={"state": state, "code": "fake-code"}, follow_redirects=False
            )

            response = auth_client.delete("/auth/oauth/github")
            assert response.status_code == 204

            linked = auth_client.get("/auth/oauth/linked")
            assert linked.json()["identities"] == []
        finally:
            _clear_overrides(auth_client)

    def test_unlinking_something_never_linked_is_not_found(self, auth_client):
        response = auth_client.delete("/auth/oauth/google")
        assert response.status_code == 404


class TestLinkedEndpoint:
    def test_requires_authentication(self, client):
        response = client.get("/auth/oauth/linked")
        assert response.status_code == 401

    def test_starts_empty_for_a_fresh_account(self, auth_client):
        response = auth_client.get("/auth/oauth/linked")
        assert response.status_code == 200
        assert response.json() == {"identities": []}
