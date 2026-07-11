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
