from fastapi import APIRouter, Cookie, Depends, Response, status

from app.api.deps import get_auth_service, get_current_user
from app.auth.service import AuthService
from app.core.config import Settings, get_settings
from app.core.exceptions import UnauthorizedError
from app.models.user import User
from app.schemas.auth import AuthResponse, LoginRequest, RegisterRequest, UserResponse

router = APIRouter(prefix="/auth", tags=["auth"])

REFRESH_COOKIE = "partha_refresh"


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


@router.post("/register", response_model=AuthResponse, status_code=status.HTTP_201_CREATED)
def register(
    request: RegisterRequest,
    response: Response,
    service: AuthService = Depends(get_auth_service),
    settings: Settings = Depends(get_settings),
) -> AuthResponse:
    user, access_token, raw_refresh = service.register(request.email, request.password)
    _set_refresh_cookie(response, raw_refresh, settings)
    return AuthResponse(access_token=access_token, user=UserResponse.model_validate(user))


@router.post("/login", response_model=AuthResponse)
def login(
    request: LoginRequest,
    response: Response,
    service: AuthService = Depends(get_auth_service),
    settings: Settings = Depends(get_settings),
) -> AuthResponse:
    user, access_token, raw_refresh = service.login(request.email, request.password)
    _set_refresh_cookie(response, raw_refresh, settings)
    return AuthResponse(access_token=access_token, user=UserResponse.model_validate(user))


@router.post("/refresh", response_model=AuthResponse)
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


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(
    refresh_token: str | None = Cookie(default=None, alias=REFRESH_COOKIE),
    service: AuthService = Depends(get_auth_service),
) -> Response:
    service.logout(refresh_token)
    response = Response(status_code=status.HTTP_204_NO_CONTENT)
    response.delete_cookie(REFRESH_COOKIE, path="/auth")
    return response


@router.get("/me", response_model=UserResponse)
def me(current_user: User = Depends(get_current_user)) -> UserResponse:
    return UserResponse.model_validate(current_user)
