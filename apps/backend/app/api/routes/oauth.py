"""Google/GitHub OAuth sign-in and account linking (#288).

Credentials-deferred build -- see the comment on issue #288 for exactly what
still needs the owner's real client id/secret plus a decided public callback
domain before this can go live. Every code path here is exercised in tests
against clearly-fake mocked provider clients (app/auth/oauth_providers.py);
nothing here makes a real network call in tests.
"""

from typing import Annotated

from fastapi import APIRouter, Body, Depends, Query, Request, Response, status
from fastapi.responses import RedirectResponse

from app.api.deps import get_current_user, get_oauth_service
from app.api.openapi import documented_responses, error_responses
from app.api.routes.auth import _set_refresh_cookie
from app.core.config import Settings, get_settings
from app.core.exceptions import ValidationServiceError
from app.models.user import User
from app.schemas.auth import (
    AuthResponse,
    OAuthLinkConfirmRequest,
    OAuthLinkedIdentitiesResponse,
    OAuthLinkedIdentity,
    OAuthProvidersResponse,
    OAuthStartResponse,
    UserResponse,
)
from app.services.oauth_service import OAuthService

router = APIRouter(prefix="/auth/oauth", tags=["auth"])

# The only two providers OAuthService is ever wired with (app/api/deps.py);
# validated here so an unsupported path segment fails fast with a normal 422
# rather than surfacing as an opaque "provider unavailable" from the service.
_KNOWN_PROVIDERS = {"google", "github"}

_PROVIDERS_EXAMPLE = {"providers": ["google"]}
_START_EXAMPLE = {"authorizeUrl": "https://accounts.google.com/o/oauth2/v2/auth?client_id=..."}
_LINKED_EXAMPLE = {
    "identities": [{"provider": "google", "email": "developer@example.com", "createdAt": "2026-07-17T00:00:00Z"}]
}
_LINK_CONFIRM_AUTH_EXAMPLE = {
    "accessToken": "example-access-token",
    "tokenType": "bearer",
    "user": {
        "id": "11111111-1111-1111-1111-111111111111",
        "email": "developer@example.com",
        "createdAt": "2026-07-17T00:00:00Z",
    },
}
_LINK_CONFIRM_REQUEST_EXAMPLE = {
    "summary": "Confirm the discovered identity belongs to this account",
    "value": {
        "pendingLinkId": "11111111-1111-1111-1111-111111111111",
        "password": "correct-horse-battery-staple",
    },
}


def _validate_provider(provider: str) -> str:
    if provider not in _KNOWN_PROVIDERS:
        raise ValidationServiceError(f"Unsupported provider: {provider}")
    return provider


def _redirect_base(request: Request, settings: Settings) -> str:
    """The frontend origin to send the browser back to once the callback
    finishes, success or error.

    Trusts only an Origin/Referer that is itself one of the configured CORS
    origins -- the same trust boundary already enforced for cross-origin
    requests -- and otherwise falls back to the first configured origin so a
    request with a missing or unrecognized header still gets a safe,
    deterministic place to land.
    """
    for header_name in ("origin", "referer"):
        header = request.headers.get(header_name)
        if not header:
            continue
        candidate = header.rstrip("/")
        for origin in settings.cors_origins:
            if candidate == origin or candidate.startswith(origin + "/"):
                return origin
    return settings.cors_origins[0]


@router.get(
    "/providers",
    response_model=OAuthProvidersResponse,
    responses=documented_responses(200, "Providers with real credentials configured.", _PROVIDERS_EXAMPLE, 429, 500),
)
def list_oauth_providers(service: OAuthService = Depends(get_oauth_service)) -> OAuthProvidersResponse:
    return OAuthProvidersResponse(providers=service.configured_providers())


@router.get(
    "/{provider}/start",
    response_model=OAuthStartResponse,
    responses=documented_responses(200, "Authorize URL to send the browser to.", _START_EXAMPLE, 422, 429, 500),
)
def start_oauth_login(
    provider: str,
    request: Request,
    settings: Settings = Depends(get_settings),
    service: OAuthService = Depends(get_oauth_service),
) -> OAuthStartResponse:
    provider = _validate_provider(provider)
    url = service.start(provider, intent="login", frontend_redirect_base=_redirect_base(request, settings))
    return OAuthStartResponse(authorize_url=url)


@router.post(
    "/{provider}/link",
    response_model=OAuthStartResponse,
    responses=documented_responses(
        200, "Authorize URL to link this provider to the caller's account.", _START_EXAMPLE, 401, 422, 429, 500
    ),
)
def start_oauth_link(
    provider: str,
    request: Request,
    settings: Settings = Depends(get_settings),
    current_user: User = Depends(get_current_user),
    service: OAuthService = Depends(get_oauth_service),
) -> OAuthStartResponse:
    provider = _validate_provider(provider)
    url = service.start(
        provider,
        intent="link",
        frontend_redirect_base=_redirect_base(request, settings),
        link_user_id=current_user.id,
    )
    return OAuthStartResponse(authorize_url=url)


@router.get(
    "/{provider}/callback",
    responses=documented_responses(
        200,
        "Always redirects (302) to the frontend's /oauth/complete route with the outcome in the query "
        "string; the schema below documents the shape only to satisfy this API's success-example "
        "convention -- no caller ever receives this body.",
        {"note": "This operation always returns a 302 redirect, never this body."},
        422,
        429,
        500,
        schema={"type": "object", "properties": {"note": {"type": "string"}}},
    ),
)
async def oauth_callback(
    provider: str,
    settings: Settings = Depends(get_settings),
    service: OAuthService = Depends(get_oauth_service),
    code: str | None = Query(default=None),
    state: str | None = Query(default=None),
    error: str | None = Query(default=None),
) -> RedirectResponse:
    """The browser lands here via a top-level navigation from the provider,
    never via an XHR/fetch call -- so the only way to hand the outcome back
    is a redirect to the frontend's own /oauth/complete route, which reads
    the query string and finishes locally (see useAuthStore.bootstrap() on
    the success path, which re-derives the access token from the refresh
    cookie this response sets)."""
    provider = _validate_provider(provider)
    if not state:
        raise ValidationServiceError("Missing OAuth state.")
    frontend_base, result = await service.complete_callback(provider, state=state, code=code, provider_error=error)

    if result.kind == "session":
        redirect = RedirectResponse(
            url=f"{frontend_base}/oauth/complete?status=success", status_code=status.HTTP_302_FOUND
        )
        _set_refresh_cookie(redirect, result.refresh_token or "", settings)
        return redirect
    if result.kind == "linked":
        return RedirectResponse(url=f"{frontend_base}/oauth/complete?status=linked", status_code=status.HTTP_302_FOUND)
    if result.kind == "pending_link":
        return RedirectResponse(
            url=f"{frontend_base}/oauth/complete?status=pending-link&pendingLinkId={result.pending_link_id}&provider={provider}",
            status_code=status.HTTP_302_FOUND,
        )
    return RedirectResponse(
        url=f"{frontend_base}/oauth/complete?status=error&reason={result.error_code or 'unknown'}",
        status_code=status.HTTP_302_FOUND,
    )


@router.post(
    "/link/confirm",
    response_model=AuthResponse,
    responses=documented_responses(200, "Linked and signed in.", _LINK_CONFIRM_AUTH_EXAMPLE, 401, 409, 422, 429, 500),
)
def confirm_oauth_link(
    body: Annotated[OAuthLinkConfirmRequest, Body(openapi_examples={"confirm": _LINK_CONFIRM_REQUEST_EXAMPLE})],
    response: Response,
    settings: Settings = Depends(get_settings),
    service: OAuthService = Depends(get_oauth_service),
) -> AuthResponse:
    user, access_token, raw_refresh = service.confirm_pending_link(body.pending_link_id, body.password)
    _set_refresh_cookie(response, raw_refresh, settings)
    return AuthResponse(access_token=access_token, user=UserResponse.model_validate(user))


@router.get(
    "/linked",
    response_model=OAuthLinkedIdentitiesResponse,
    responses=documented_responses(200, "The caller's linked provider identities.", _LINKED_EXAMPLE, 401, 429, 500),
)
def list_linked_identities(
    current_user: User = Depends(get_current_user),
    service: OAuthService = Depends(get_oauth_service),
) -> OAuthLinkedIdentitiesResponse:
    identities = service.linked_identities(current_user.id)
    return OAuthLinkedIdentitiesResponse(
        identities=[
            OAuthLinkedIdentity(provider=identity.provider, email=identity.email, created_at=identity.created_at)
            for identity in identities
        ]
    )


@router.delete(
    "/{provider}",
    status_code=status.HTTP_204_NO_CONTENT,
    responses=error_responses(401, 404, 422, 429, 500),
)
def unlink_oauth_provider(
    provider: str,
    current_user: User = Depends(get_current_user),
    service: OAuthService = Depends(get_oauth_service),
) -> Response:
    provider = _validate_provider(provider)
    service.unlink(current_user, provider)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
