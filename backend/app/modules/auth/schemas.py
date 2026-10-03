import re
import uuid
from datetime import datetime
from typing import Annotated, Literal

from pydantic import (
    AfterValidator,
    BaseModel,
    ConfigDict,
    Field,
    StringConstraints,
    field_validator,
)

from app.core.db import utcnow

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def _normalize_email(value: str) -> str:
    value = value.strip().lower()
    if len(value) > 320 or not _EMAIL_RE.match(value):
        raise ValueError("not a valid e-mail address")
    return value


Email = Annotated[str, AfterValidator(_normalize_email)]
DisplayName = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=100)]


class RegisterRequest(BaseModel):
    email: Email
    display_name: DisplayName
    password: str = Field(min_length=10, max_length=128)


class LoginRequest(BaseModel):
    email: Email
    password: str = Field(max_length=128)


class RefreshRequest(BaseModel):
    refresh_token: str = Field(max_length=256)


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: str
    display_name: str
    role: Literal["user", "admin"]
    created_at: datetime


class UserLookupOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    display_name: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: Literal["bearer"] = "bearer"
    expires_in: int = Field(description="Lifetime of the access token in seconds")


class AuthResponse(TokenResponse):
    user: UserOut


class Profile(BaseModel):
    """Optional data for the calorie estimate; every field may be empty."""

    model_config = ConfigDict(from_attributes=True)

    weight_kg: float | None = Field(default=None, ge=20, le=400)
    birth_year: int | None = Field(default=None, ge=1900)
    # Only `female` and `male` select a sex-specific calorie formula.
    sex: Literal["female", "male", "trans", "undisclosed"] | None = None
    max_heart_rate: int | None = Field(default=None, ge=60, le=250)
    resting_heart_rate: int | None = Field(default=None, ge=20, le=150)

    @field_validator("birth_year")
    @classmethod
    def _not_in_future(cls, value: int | None) -> int | None:
        if value is not None and value > utcnow().year:
            raise ValueError("birth_year must not be in the future")
        return value
