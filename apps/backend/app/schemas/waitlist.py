from typing import Literal

from pydantic import EmailStr, Field

from app.schemas.base import CamelModel


class WaitlistSignupRequest(CamelModel):
    email: EmailStr
    name: str | None = Field(default=None, max_length=200)


class WaitlistSignupResponse(CamelModel):
    status: Literal["ok"]
