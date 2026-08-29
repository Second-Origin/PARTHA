from datetime import datetime
from typing import Literal

from pydantic import EmailStr, Field

from app.schemas.base import CamelModel

# Minimum length is the only enforced policy; complexity rules push users
# toward predictable substitutions instead of longer passphrases.
PASSWORD_MIN_LENGTH = 10
PASSWORD_MAX_LENGTH = 128


class RegisterRequest(CamelModel):
    email: EmailStr
    password: str = Field(min_length=PASSWORD_MIN_LENGTH, max_length=PASSWORD_MAX_LENGTH)


class LoginRequest(CamelModel):
    email: EmailStr
    # No minimum here: login validates against the stored hash, and rejecting
    # short inputs early would leak the registration policy on the login form.
    password: str = Field(max_length=PASSWORD_MAX_LENGTH)


class UserResponse(CamelModel):
    id: str
    email: str
    created_at: datetime


class AuthResponse(CamelModel):
    access_token: str
    token_type: Literal["bearer"] = "bearer"
    user: UserResponse


class AccountDeletionRequest(CamelModel):
    # No minimum length here for the same reason as LoginRequest: this
    # verifies against the stored hash, and a short-password rejection would
    # only leak the registration policy without adding any real protection.
    password: str = Field(max_length=PASSWORD_MAX_LENGTH)
    # Deliberate confirmation gate: the caller must type back their own
    # account email, not just click a button, before an irreversible delete.
    confirm_email: EmailStr


class OAuthProvidersResponse(CamelModel):
    """Which providers have real credentials configured (#288) -- the
    frontend only ever renders a "Continue with ..." button for one of
    these, the same capability-gating pattern as GET /ai/providers."""

    providers: list[str]


class OAuthStartResponse(CamelModel):
    authorize_url: str


class OAuthLinkConfirmRequest(CamelModel):
    pending_link_id: str = Field(min_length=1, max_length=36)
    # No minimum length: same reasoning as LoginRequest, this only ever
    # verifies against an existing stored hash.
    password: str = Field(max_length=PASSWORD_MAX_LENGTH)


class OAuthLinkedIdentity(CamelModel):
    provider: str
    email: str | None
    created_at: datetime


class OAuthLinkedIdentitiesResponse(CamelModel):
    identities: list[OAuthLinkedIdentity]
