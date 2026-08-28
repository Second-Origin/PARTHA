"""Google and GitHub OAuth provider clients (#288).

Credentials-deferred build: no real OAuth application has been registered
for either provider yet (see the comment on issue #288 for what a real
go-live still needs). Everything here is fully implemented and exercised
end-to-end in tests against clearly-fake mocked HTTP responses -- nothing in
this module makes a real network call in tests, and going live only needs a
real client id/secret plus the redirect URIs registered with each
provider's console.

Google uses Authorization Code + PKCE + OIDC: the token exchange returns a
signed id_token whose signature is verified against Google's published JWKS,
whose issuer/audience are checked, and whose nonce is matched against the
flow that started it -- the identity comes from that verified token, never
from an unauthenticated userinfo call. GitHub OAuth Apps support neither
PKCE nor OIDC: the exchange returns an opaque access token that is then used
to call GitHub's REST API for the account's identity and verified email.

Both clients share one interface (OAuthProviderClient) so OAuthService never
branches on which provider it's talking to.
"""

from __future__ import annotations

import base64
import hashlib
import secrets
from dataclasses import dataclass
from typing import Protocol
from urllib.parse import urlencode

import httpx
import jwt
from cryptography.hazmat.primitives.asymmetric.rsa import RSAPublicKey
from jwt import PyJWTError
from jwt.algorithms import RSAAlgorithm

from app.core.config import Settings

GOOGLE_AUTHORIZE_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_JWKS_URL = "https://www.googleapis.com/oauth2/v3/certs"
GOOGLE_ISSUERS = {"https://accounts.google.com", "accounts.google.com"}

GITHUB_AUTHORIZE_URL = "https://github.com/login/oauth/authorize"
GITHUB_TOKEN_URL = "https://github.com/login/oauth/access_token"
GITHUB_USER_URL = "https://api.github.com/user"
GITHUB_EMAILS_URL = "https://api.github.com/user/emails"

_HTTP_TIMEOUT_SECONDS = 10.0


class OAuthProviderError(Exception):
    """Any provider-side failure: a bad/expired code, a network error, an
    invalid or expired id_token, a provider outage. Callers translate this
    into one generic user-facing message; the detail stays server-side in
    logs so it can never be used to probe provider internals."""


@dataclass(frozen=True)
class OAuthIdentityInfo:
    subject: str
    email: str | None
    email_verified: bool
    display_name: str | None


def generate_pkce_pair() -> tuple[str, str]:
    """Return (code_verifier, code_challenge) for RFC 7636 S256 PKCE."""
    verifier = secrets.token_urlsafe(64)[:128]
    digest = hashlib.sha256(verifier.encode("ascii")).digest()
    challenge = base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")
    return verifier, challenge


def generate_state() -> str:
    return secrets.token_urlsafe(32)


def generate_nonce() -> str:
    return secrets.token_urlsafe(32)


class OAuthProviderClient(Protocol):
    def is_configured(self) -> bool: ...

    def authorize_url(self, *, redirect_uri: str, state: str, code_challenge: str, nonce: str) -> str: ...

    async def resolve_identity(
        self, *, code: str, redirect_uri: str, code_verifier: str | None, nonce: str | None
    ) -> OAuthIdentityInfo: ...


def _verify_google_id_token(id_token: str, jwks: dict, *, client_id: str) -> dict:
    try:
        header = jwt.get_unverified_header(id_token)
    except PyJWTError as exc:
        raise OAuthProviderError("Malformed Google id_token.") from exc
    kid = header.get("kid")
    matching = next((key for key in jwks.get("keys", []) if key.get("kid") == kid), None)
    if matching is None:
        raise OAuthProviderError("No matching Google JWKS key for id_token.")
    try:
        public_key = RSAAlgorithm.from_jwk(matching)
        if not isinstance(public_key, RSAPublicKey):
            # A JWKS entry is only ever meant to publish a public key; this
            # would mean either a malformed response or a `from_jwk` result
            # this code doesn't expect, either way not safe to verify with.
            raise OAuthProviderError("Google JWKS key is not a usable RSA public key.")
        claims = jwt.decode(
            id_token,
            key=public_key,
            algorithms=["RS256"],
            audience=client_id,
            issuer=list(GOOGLE_ISSUERS),
        )
    except PyJWTError as exc:
        raise OAuthProviderError("Google id_token failed verification.") from exc
    return claims


class GoogleOAuthClient:
    def __init__(self, settings: Settings, http_client: httpx.AsyncClient | None = None) -> None:
        self._settings = settings
        # Tests inject a fake client so nothing here ever makes a real
        # network call; production leaves this None and a short-lived client
        # is opened per call.
        self._http = http_client

    def is_configured(self) -> bool:
        return bool(self._settings.google_oauth_client_id and self._settings.google_oauth_client_secret)

    def authorize_url(self, *, redirect_uri: str, state: str, code_challenge: str, nonce: str) -> str:
        params = {
            "client_id": self._settings.google_oauth_client_id,
            "redirect_uri": redirect_uri,
            "response_type": "code",
            "scope": "openid email profile",
            "state": state,
            "code_challenge": code_challenge,
            "code_challenge_method": "S256",
            "nonce": nonce,
            "access_type": "online",
            "prompt": "select_account",
        }
        return f"{GOOGLE_AUTHORIZE_URL}?{urlencode(params)}"

    async def resolve_identity(
        self, *, code: str, redirect_uri: str, code_verifier: str | None, nonce: str | None
    ) -> OAuthIdentityInfo:
        client = self._http or httpx.AsyncClient(timeout=_HTTP_TIMEOUT_SECONDS, follow_redirects=False)
        owns_client = self._http is None
        try:
            token_response = await client.post(
                GOOGLE_TOKEN_URL,
                data={
                    "client_id": self._settings.google_oauth_client_id,
                    "client_secret": self._settings.google_oauth_client_secret,
                    "code": code,
                    "code_verifier": code_verifier or "",
                    "redirect_uri": redirect_uri,
                    "grant_type": "authorization_code",
                },
            )
            if token_response.status_code != 200:
                raise OAuthProviderError(f"Google token exchange failed: {token_response.status_code}")
            token_body = token_response.json()
            id_token = token_body.get("id_token")
            if not id_token:
                raise OAuthProviderError("Google token response missing id_token.")

            jwks_response = await client.get(GOOGLE_JWKS_URL)
            if jwks_response.status_code != 200:
                raise OAuthProviderError(f"Failed to fetch Google JWKS: {jwks_response.status_code}")
            jwks = jwks_response.json()
        except httpx.HTTPError as exc:
            raise OAuthProviderError("Network error talking to Google.") from exc
        finally:
            if owns_client:
                await client.aclose()

        claims = _verify_google_id_token(id_token, jwks, client_id=self._settings.google_oauth_client_id)
        if claims.get("nonce") != nonce:
            raise OAuthProviderError("Google id_token nonce mismatch.")
        subject = claims.get("sub")
        if not subject:
            raise OAuthProviderError("Google id_token missing sub claim.")
        return OAuthIdentityInfo(
            subject=str(subject),
            email=claims.get("email"),
            email_verified=bool(claims.get("email_verified", False)),
            display_name=claims.get("name"),
        )


class GitHubOAuthClient:
    def __init__(self, settings: Settings, http_client: httpx.AsyncClient | None = None) -> None:
        self._settings = settings
        self._http = http_client

    def is_configured(self) -> bool:
        return bool(self._settings.github_oauth_client_id and self._settings.github_oauth_client_secret)

    def authorize_url(self, *, redirect_uri: str, state: str, code_challenge: str, nonce: str) -> str:
        # GitHub OAuth Apps support neither PKCE nor OIDC; code_challenge and
        # nonce are accepted (to keep the interface uniform with Google) and
        # simply unused.
        params = {
            "client_id": self._settings.github_oauth_client_id,
            "redirect_uri": redirect_uri,
            "scope": "read:user user:email",
            "state": state,
            "allow_signup": "true",
        }
        return f"{GITHUB_AUTHORIZE_URL}?{urlencode(params)}"

    async def resolve_identity(
        self, *, code: str, redirect_uri: str, code_verifier: str | None, nonce: str | None
    ) -> OAuthIdentityInfo:
        client = self._http or httpx.AsyncClient(timeout=_HTTP_TIMEOUT_SECONDS, follow_redirects=False)
        owns_client = self._http is None
        try:
            token_response = await client.post(
                GITHUB_TOKEN_URL,
                headers={"Accept": "application/json"},
                data={
                    "client_id": self._settings.github_oauth_client_id,
                    "client_secret": self._settings.github_oauth_client_secret,
                    "code": code,
                    "redirect_uri": redirect_uri,
                },
            )
            if token_response.status_code != 200:
                raise OAuthProviderError(f"GitHub token exchange failed: {token_response.status_code}")
            token_body = token_response.json()
            access_token = token_body.get("access_token")
            if not access_token or token_body.get("error"):
                raise OAuthProviderError(f"GitHub token exchange denied: {token_body.get('error', 'unknown')}")

            auth_header = {"Authorization": f"Bearer {access_token}", "Accept": "application/vnd.github+json"}
            user_response = await client.get(GITHUB_USER_URL, headers=auth_header)
            if user_response.status_code != 200:
                raise OAuthProviderError(f"GitHub user lookup failed: {user_response.status_code}")
            user_body = user_response.json()
            subject = user_body.get("id")
            if subject is None:
                raise OAuthProviderError("GitHub user response missing id.")

            email = user_body.get("email")
            email_verified = bool(email)
            if not email:
                emails_response = await client.get(GITHUB_EMAILS_URL, headers=auth_header)
                if emails_response.status_code == 200:
                    for entry in emails_response.json():
                        if entry.get("primary") and entry.get("verified"):
                            email = entry.get("email")
                            email_verified = True
                            break
        except httpx.HTTPError as exc:
            raise OAuthProviderError("Network error talking to GitHub.") from exc
        finally:
            if owns_client:
                await client.aclose()

        return OAuthIdentityInfo(
            subject=str(subject),
            email=email,
            email_verified=email_verified,
            display_name=user_body.get("name") or user_body.get("login"),
        )
