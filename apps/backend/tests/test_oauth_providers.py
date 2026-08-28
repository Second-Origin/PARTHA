"""Unit tests for the Google/GitHub OAuth provider clients (#288).

Every HTTP call here goes through httpx.MockTransport -- a clearly-fake,
in-process handler, never a real network call to Google or GitHub. The
Google id_token is a real RS256-signed JWT built from a throwaway keypair
generated for the test, so signature verification, issuer/audience/nonce
checks, and JWKS key lookup are exercised for real rather than stubbed out.
"""

import asyncio
import json
import time

import httpx
import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from jwt.algorithms import RSAAlgorithm

from app.auth.oauth_providers import (
    GITHUB_EMAILS_URL,
    GITHUB_TOKEN_URL,
    GITHUB_USER_URL,
    GOOGLE_JWKS_URL,
    GOOGLE_TOKEN_URL,
    GitHubOAuthClient,
    GoogleOAuthClient,
    OAuthProviderError,
    generate_nonce,
    generate_pkce_pair,
    generate_state,
)
from app.core.config import Settings

FAKE_GOOGLE_CLIENT_ID = "fake-google-client-id.apps.googleusercontent.com"
FAKE_GOOGLE_CLIENT_SECRET = "fake-google-client-secret"  # noqa: S105 -- test double, not a real secret
FAKE_GITHUB_CLIENT_ID = "fake-github-client-id"
FAKE_GITHUB_CLIENT_SECRET = "fake-github-client-secret"  # noqa: S105 -- test double, not a real secret


def _settings(**overrides: str) -> Settings:
    values = {
        "google_oauth_client_id": FAKE_GOOGLE_CLIENT_ID,
        "google_oauth_client_secret": FAKE_GOOGLE_CLIENT_SECRET,
        "github_oauth_client_id": FAKE_GITHUB_CLIENT_ID,
        "github_oauth_client_secret": FAKE_GITHUB_CLIENT_SECRET,
    }
    values.update(overrides)
    return Settings(**values)


@pytest.fixture(scope="module")
def rsa_keypair():
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    return private_key, private_key.public_key()


def _jwk_for(public_key, kid: str) -> dict:
    jwk = json.loads(RSAAlgorithm.to_jwk(public_key))
    jwk.update(kid=kid, use="sig", alg="RS256")
    return jwk


def _make_id_token(
    private_key,
    *,
    kid: str,
    audience: str,
    nonce: str,
    subject: str = "108234567890123456789",
    email: str | None = "developer@example.com",
    email_verified: bool = True,
    issuer: str = "https://accounts.google.com",
    expired: bool = False,
) -> str:
    now = int(time.time())
    claims = {
        "iss": issuer,
        "aud": audience,
        "sub": subject,
        "nonce": nonce,
        "iat": now,
        "exp": now + (-60 if expired else 3600),
        "name": "Test Developer",
    }
    if email is not None:
        claims["email"] = email
        claims["email_verified"] = email_verified
    return jwt.encode(claims, private_key, algorithm="RS256", headers={"kid": kid})


def _google_transport(
    *, id_token: str | None, jwks: list[dict], token_status: int = 200, jwks_status: int = 200
) -> httpx.MockTransport:
    def handler(request: httpx.Request) -> httpx.Response:
        if str(request.url) == GOOGLE_TOKEN_URL:
            body = {"id_token": id_token} if id_token else {"error": "invalid_grant"}
            return httpx.Response(token_status, json=body)
        if str(request.url) == GOOGLE_JWKS_URL:
            return httpx.Response(jwks_status, json={"keys": jwks})
        raise AssertionError(f"Unexpected request to {request.url}")

    return httpx.MockTransport(handler)


def _run(coro):
    return asyncio.run(coro)


class TestPkceAndStateHelpers:
    def test_pkce_pair_matches_s256_challenge(self):
        import base64
        import hashlib

        verifier, challenge = generate_pkce_pair()
        expected = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode("ascii")).digest()).rstrip(b"=").decode()
        assert challenge == expected
        assert len(verifier) <= 128

    def test_state_and_nonce_are_high_entropy_and_unique(self):
        values = {generate_state() for _ in range(20)} | {generate_nonce() for _ in range(20)}
        assert len(values) == 40
        assert all(len(v) >= 32 for v in values)


class TestGoogleOAuthClient:
    def test_is_configured_requires_both_id_and_secret(self):
        assert GoogleOAuthClient(_settings()).is_configured() is True
        assert GoogleOAuthClient(_settings(google_oauth_client_secret="")).is_configured() is False
        assert GoogleOAuthClient(_settings(google_oauth_client_id="")).is_configured() is False

    def test_authorize_url_carries_pkce_state_and_nonce(self):
        client = GoogleOAuthClient(_settings())
        url = client.authorize_url(
            redirect_uri="https://api.example.test/auth/oauth/google/callback",
            state="the-state",
            code_challenge="the-challenge",
            nonce="the-nonce",
        )
        assert "client_id=" + FAKE_GOOGLE_CLIENT_ID in url
        assert "state=the-state" in url
        assert "code_challenge=the-challenge" in url
        assert "code_challenge_method=S256" in url
        assert "nonce=the-nonce" in url
        assert "response_type=code" in url

    def test_resolve_identity_verifies_signature_and_returns_identity(self, rsa_keypair):
        private_key, public_key = rsa_keypair
        kid = "test-key-1"
        nonce = "expected-nonce-value"
        id_token = _make_id_token(private_key, kid=kid, audience=FAKE_GOOGLE_CLIENT_ID, nonce=nonce)
        transport = _google_transport(id_token=id_token, jwks=[_jwk_for(public_key, kid)])
        client = GoogleOAuthClient(_settings(), http_client=httpx.AsyncClient(transport=transport))

        identity = _run(
            client.resolve_identity(
                code="fake-code",
                redirect_uri="https://api.example.test/auth/oauth/google/callback",
                code_verifier="verifier",
                nonce=nonce,
            )
        )
        assert identity.subject == "108234567890123456789"
        assert identity.email == "developer@example.com"
        assert identity.email_verified is True
        assert identity.display_name == "Test Developer"

    def test_resolve_identity_rejects_nonce_mismatch(self, rsa_keypair):
        private_key, public_key = rsa_keypair
        kid = "test-key-2"
        id_token = _make_id_token(private_key, kid=kid, audience=FAKE_GOOGLE_CLIENT_ID, nonce="actual-nonce")
        transport = _google_transport(id_token=id_token, jwks=[_jwk_for(public_key, kid)])
        client = GoogleOAuthClient(_settings(), http_client=httpx.AsyncClient(transport=transport))

        with pytest.raises(OAuthProviderError, match="nonce"):
            _run(
                client.resolve_identity(
                    code="fake-code",
                    redirect_uri="https://api.example.test/auth/oauth/google/callback",
                    code_verifier="verifier",
                    nonce="different-nonce",
                )
            )

    def test_resolve_identity_rejects_wrong_audience(self, rsa_keypair):
        private_key, public_key = rsa_keypair
        kid = "test-key-3"
        nonce = "n"
        id_token = _make_id_token(private_key, kid=kid, audience="someone-elses-client-id", nonce=nonce)
        transport = _google_transport(id_token=id_token, jwks=[_jwk_for(public_key, kid)])
        client = GoogleOAuthClient(_settings(), http_client=httpx.AsyncClient(transport=transport))

        with pytest.raises(OAuthProviderError):
            _run(
                client.resolve_identity(
                    code="fake-code",
                    redirect_uri="https://api.example.test/auth/oauth/google/callback",
                    code_verifier="verifier",
                    nonce=nonce,
                )
            )

    def test_resolve_identity_rejects_wrong_issuer(self, rsa_keypair):
        private_key, public_key = rsa_keypair
        kid = "test-key-4"
        nonce = "n"
        id_token = _make_id_token(
            private_key, kid=kid, audience=FAKE_GOOGLE_CLIENT_ID, nonce=nonce, issuer="https://not-google.example"
        )
        transport = _google_transport(id_token=id_token, jwks=[_jwk_for(public_key, kid)])
        client = GoogleOAuthClient(_settings(), http_client=httpx.AsyncClient(transport=transport))

        with pytest.raises(OAuthProviderError):
            _run(
                client.resolve_identity(
                    code="fake-code",
                    redirect_uri="https://api.example.test/auth/oauth/google/callback",
                    code_verifier="verifier",
                    nonce=nonce,
                )
            )

    def test_resolve_identity_rejects_expired_token(self, rsa_keypair):
        private_key, public_key = rsa_keypair
        kid = "test-key-5"
        nonce = "n"
        id_token = _make_id_token(private_key, kid=kid, audience=FAKE_GOOGLE_CLIENT_ID, nonce=nonce, expired=True)
        transport = _google_transport(id_token=id_token, jwks=[_jwk_for(public_key, kid)])
        client = GoogleOAuthClient(_settings(), http_client=httpx.AsyncClient(transport=transport))

        with pytest.raises(OAuthProviderError):
            _run(
                client.resolve_identity(
                    code="fake-code",
                    redirect_uri="https://api.example.test/auth/oauth/google/callback",
                    code_verifier="verifier",
                    nonce=nonce,
                )
            )

    def test_resolve_identity_rejects_unknown_kid(self, rsa_keypair):
        _private_key, public_key = rsa_keypair
        other_private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        nonce = "n"
        # Signed by a key whose kid never appears in the JWKS response.
        id_token = _make_id_token(other_private_key, kid="unknown-kid", audience=FAKE_GOOGLE_CLIENT_ID, nonce=nonce)
        transport = _google_transport(id_token=id_token, jwks=[_jwk_for(public_key, "test-key-6")])
        client = GoogleOAuthClient(_settings(), http_client=httpx.AsyncClient(transport=transport))

        with pytest.raises(OAuthProviderError, match="JWKS"):
            _run(
                client.resolve_identity(
                    code="fake-code",
                    redirect_uri="https://api.example.test/auth/oauth/google/callback",
                    code_verifier="verifier",
                    nonce=nonce,
                )
            )

    def test_resolve_identity_rejects_forged_signature(self, rsa_keypair):
        """A token signed by a DIFFERENT key than the one published under its
        own kid must fail -- otherwise an attacker could publish any claims
        under someone else's kid label."""
        _private_key, public_key = rsa_keypair
        forger_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        kid = "shared-kid-label"
        nonce = "n"
        forged_token = _make_id_token(forger_key, kid=kid, audience=FAKE_GOOGLE_CLIENT_ID, nonce=nonce)
        # JWKS publishes the REAL public key under the same kid the forger used.
        transport = _google_transport(id_token=forged_token, jwks=[_jwk_for(public_key, kid)])
        client = GoogleOAuthClient(_settings(), http_client=httpx.AsyncClient(transport=transport))

        with pytest.raises(OAuthProviderError):
            _run(
                client.resolve_identity(
                    code="fake-code",
                    redirect_uri="https://api.example.test/auth/oauth/google/callback",
                    code_verifier="verifier",
                    nonce=nonce,
                )
            )

    def test_resolve_identity_handles_token_exchange_denial(self):
        transport = _google_transport(id_token=None, jwks=[], token_status=400)
        client = GoogleOAuthClient(_settings(), http_client=httpx.AsyncClient(transport=transport))

        with pytest.raises(OAuthProviderError):
            _run(
                client.resolve_identity(
                    code="bad-code",
                    redirect_uri="https://api.example.test/auth/oauth/google/callback",
                    code_verifier="verifier",
                    nonce="n",
                )
            )

    def test_resolve_identity_handles_jwks_fetch_failure(self, rsa_keypair):
        private_key, _public_key = rsa_keypair
        id_token = _make_id_token(private_key, kid="k", audience=FAKE_GOOGLE_CLIENT_ID, nonce="n")
        transport = _google_transport(id_token=id_token, jwks=[], jwks_status=503)
        client = GoogleOAuthClient(_settings(), http_client=httpx.AsyncClient(transport=transport))

        with pytest.raises(OAuthProviderError):
            _run(
                client.resolve_identity(
                    code="fake-code",
                    redirect_uri="https://api.example.test/auth/oauth/google/callback",
                    code_verifier="verifier",
                    nonce="n",
                )
            )

    def test_resolve_identity_treats_unverified_email_as_such(self, rsa_keypair):
        private_key, public_key = rsa_keypair
        kid = "test-key-7"
        nonce = "n"
        id_token = _make_id_token(
            private_key, kid=kid, audience=FAKE_GOOGLE_CLIENT_ID, nonce=nonce, email_verified=False
        )
        transport = _google_transport(id_token=id_token, jwks=[_jwk_for(public_key, kid)])
        client = GoogleOAuthClient(_settings(), http_client=httpx.AsyncClient(transport=transport))

        identity = _run(
            client.resolve_identity(
                code="fake-code",
                redirect_uri="https://api.example.test/auth/oauth/google/callback",
                code_verifier="verifier",
                nonce=nonce,
            )
        )
        assert identity.email_verified is False


def _github_transport(
    *,
    token_body: dict | None = None,
    token_status: int = 200,
    user_body: dict | None = None,
    user_status: int = 200,
    emails_body: list[dict] | None = None,
    emails_status: int = 200,
) -> httpx.MockTransport:
    def handler(request: httpx.Request) -> httpx.Response:
        if str(request.url) == GITHUB_TOKEN_URL:
            return httpx.Response(
                token_status, json=token_body if token_body is not None else {"access_token": "fake-access-token"}
            )
        if str(request.url) == GITHUB_USER_URL:
            return httpx.Response(
                user_status, json=user_body if user_body is not None else {"id": 4242, "login": "octocat"}
            )
        if str(request.url) == GITHUB_EMAILS_URL:
            return httpx.Response(emails_status, json=emails_body if emails_body is not None else [])
        raise AssertionError(f"Unexpected request to {request.url}")

    return httpx.MockTransport(handler)


class TestGitHubOAuthClient:
    def test_is_configured_requires_both_id_and_secret(self):
        assert GitHubOAuthClient(_settings()).is_configured() is True
        assert GitHubOAuthClient(_settings(github_oauth_client_secret="")).is_configured() is False

    def test_authorize_url_ignores_pkce_extras(self):
        client = GitHubOAuthClient(_settings())
        url = client.authorize_url(
            redirect_uri="https://api.example.test/auth/oauth/github/callback",
            state="the-state",
            code_challenge="unused",
            nonce="unused",
        )
        assert "client_id=" + FAKE_GITHUB_CLIENT_ID in url
        assert "state=the-state" in url
        assert "code_challenge" not in url

    def test_resolve_identity_uses_public_email_when_present(self):
        transport = _github_transport(
            user_body={"id": 555, "login": "octocat", "name": "The Octocat", "email": "octo@example.com"}
        )
        client = GitHubOAuthClient(_settings(), http_client=httpx.AsyncClient(transport=transport))

        identity = _run(
            client.resolve_identity(
                code="fake-code",
                redirect_uri="https://api.example.test/auth/oauth/github/callback",
                code_verifier=None,
                nonce=None,
            )
        )
        assert identity.subject == "555"
        assert identity.email == "octo@example.com"
        assert identity.email_verified is True
        assert identity.display_name == "The Octocat"

    def test_resolve_identity_falls_back_to_verified_primary_email(self):
        transport = _github_transport(
            user_body={"id": 555, "login": "octocat", "email": None},
            emails_body=[
                {"email": "secondary@example.com", "primary": False, "verified": True},
                {"email": "primary@example.com", "primary": True, "verified": True},
            ],
        )
        client = GitHubOAuthClient(_settings(), http_client=httpx.AsyncClient(transport=transport))

        identity = _run(
            client.resolve_identity(
                code="fake-code",
                redirect_uri="https://api.example.test/auth/oauth/github/callback",
                code_verifier=None,
                nonce=None,
            )
        )
        assert identity.email == "primary@example.com"
        assert identity.email_verified is True
        assert identity.display_name == "octocat"

    def test_resolve_identity_leaves_email_unset_when_none_verified(self):
        transport = _github_transport(
            user_body={"id": 555, "login": "octocat", "email": None},
            emails_body=[{"email": "unverified@example.com", "primary": True, "verified": False}],
        )
        client = GitHubOAuthClient(_settings(), http_client=httpx.AsyncClient(transport=transport))

        identity = _run(
            client.resolve_identity(
                code="fake-code",
                redirect_uri="https://api.example.test/auth/oauth/github/callback",
                code_verifier=None,
                nonce=None,
            )
        )
        assert identity.email is None
        assert identity.email_verified is False

    def test_resolve_identity_rejects_denied_token_exchange(self):
        transport = _github_transport(token_body={"error": "bad_verification_code"})
        client = GitHubOAuthClient(_settings(), http_client=httpx.AsyncClient(transport=transport))

        with pytest.raises(OAuthProviderError):
            _run(
                client.resolve_identity(
                    code="bad-code",
                    redirect_uri="https://api.example.test/auth/oauth/github/callback",
                    code_verifier=None,
                    nonce=None,
                )
            )

    def test_resolve_identity_rejects_failed_user_lookup(self):
        transport = _github_transport(user_status=401, user_body={"message": "Bad credentials"})
        client = GitHubOAuthClient(_settings(), http_client=httpx.AsyncClient(transport=transport))

        with pytest.raises(OAuthProviderError):
            _run(
                client.resolve_identity(
                    code="fake-code",
                    redirect_uri="https://api.example.test/auth/oauth/github/callback",
                    code_verifier=None,
                    nonce=None,
                )
            )
