from typing import Annotated

from fastapi import APIRouter, Body, Cookie, Depends, Response, status

from app.api.deps import get_auth_service, get_current_user
from app.api.openapi import documented_responses, error_responses, suppress_automatic_validation_error
from app.auth.service import AuthService
from app.core.config import Settings, get_settings
from app.core.exceptions import UnauthorizedError
from app.models.user import User
from app.schemas.auth import AuthResponse, LoginRequest, RegisterRequest, UserResponse

router = APIRouter(prefix="/auth", tags=["auth"])

REFRESH_COOKIE = "partha_refresh"

_USER_EXAMPLE = {
    "id": "11111111-1111-1111-1111-111111111111",
    "email": "developer@example.com",
    "createdAt": "2026-07-17T00:00:00Z",
}
_AUTH_RESPONSE_EXAMPLE = {
    "accessToken": "example-access-token",
    "tokenType": "bearer",
    "user": _USER_EXAMPLE,
}
_REGISTER_EXAMPLE = {
    "summary": "Create an account",
    "value": {"email": "developer@example.com", "password": "correct-horse-battery-staple"},
}
_LOGIN_EXAMPLE = {
    "summary": "Sign in to an existing account",
    "value": {"email": "developer@example.com", "password": "correct-horse-battery-staple"},
}


def _set_refresh_cookie(response: Response, raw_token: str, settings: Settings) -> None:
    response.set_cookie(
        key=REFRESH_COOKIE,
        value=raw_token,
        max_age=settings.refresh_token_ttl_seconds,
        httponly=True,
        samesite="lax",
        # Secure cookies would be dropped over plain-http local development.
        secure=settings.app_env not in {"development", "test"},
        path="/auth",
    )


@router.post(
    "/register",
    response_model=AuthResponse,
    status_code=status.HTTP_201_CREATED,
    responses=documented_responses(
        status.HTTP_201_CREATED,
        "Account created and a refresh-cookie session started.",
        _AUTH_RESPONSE_EXAMPLE,
        409,
        422,
        429,
        500,
    ),
)
def register(
    request: Annotated[RegisterRequest, Body(openapi_examples={"registration": _REGISTER_EXAMPLE})],
    response: Response,
    service: AuthService = Depends(get_auth_service),
    settings: Settings = Depends(get_settings),
) -> AuthResponse:
    user, access_token, raw_refresh = service.register(request.email, request.password)
    _set_refresh_cookie(response, raw_refresh, settings)
    return AuthResponse(access_token=access_token, user=UserResponse.model_validate(user))


@router.post(
    "/login",
    response_model=AuthResponse,
    responses=documented_responses(
        status.HTTP_200_OK,
        "Authenticated session with an access token and refresh cookie.",
        _AUTH_RESPONSE_EXAMPLE,
        401,
        422,
        429,
        500,
    ),
)
def login(
    request: Annotated[LoginRequest, Body(openapi_examples={"login": _LOGIN_EXAMPLE})],
    response: Response,
    service: AuthService = Depends(get_auth_service),
    settings: Settings = Depends(get_settings),
) -> AuthResponse:
    user, access_token, raw_refresh = service.login(request.email, request.password)
    _set_refresh_cookie(response, raw_refresh, settings)
    return AuthResponse(access_token=access_token, user=UserResponse.model_validate(user))


@router.post(
    "/refresh",
    response_model=AuthResponse,
    responses=documented_responses(
        status.HTTP_200_OK,
        "Access token renewed and the refresh token rotated.",
        _AUTH_RESPONSE_EXAMPLE,
        401,
        422,
        429,
        500,
    ),
)
def refresh(
    response: Response,
    refresh_token: str | None = Cookie(default=None, alias=REFRESH_COOKIE),
    service: AuthService = Depends(get_auth_service),
    settings: Settings = Depends(get_settings),
) -> AuthResponse:
    if not refresh_token:
        raise UnauthorizedError("Missing refresh token.")
    user, access_token, raw_refresh = service.refresh(refresh_token)
    _set_refresh_cookie(response, raw_refresh, settings)
    return AuthResponse(access_token=access_token, user=UserResponse.model_validate(user))


@router.post(
    "/logout",
    status_code=status.HTTP_204_NO_CONTENT,
    responses=error_responses(429, 500),
    openapi_extra=suppress_automatic_validation_error(),
)
def logout(
    refresh_token: str | None = Cookie(default=None, alias=REFRESH_COOKIE),
    service: AuthService = Depends(get_auth_service),
) -> Response:
    service.logout(refresh_token)
    response = Response(status_code=status.HTTP_204_NO_CONTENT)
    response.delete_cookie(REFRESH_COOKIE, path="/auth")
    return response


@router.get(
    "/me",
    response_model=UserResponse,
    responses=documented_responses(
        status.HTTP_200_OK,
        "The authenticated user.",
        _USER_EXAMPLE,
        401,
        429,
        500,
    ),
)
def me(current_user: User = Depends(get_current_user)) -> UserResponse:
    return UserResponse.model_validate(current_user)
