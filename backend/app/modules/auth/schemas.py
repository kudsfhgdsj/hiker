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


# The rules for passwords are checked in passwords.py, which also explains them.
Password = Annotated[str, Field(max_length=128)]
OneTimeCode = Annotated[str, Field(max_length=32)]


class RegisterRequest(BaseModel):
    email: Email
    display_name: DisplayName
    password: Password


class LoginRequest(BaseModel):
    email: Email
    password: str = Field(max_length=128)
    code: OneTimeCode | None = Field(
        default=None,
        description="Code of the authenticator app, or a recovery code; needed once the "
        "second factor is set up",
    )


class PasswordChange(BaseModel):
    current_password: str = Field(max_length=128)
    new_password: Password


class CodeRequest(BaseModel):
    code: OneTimeCode


class SecondStepRequest(BaseModel):
    mfa_token: str = Field(max_length=1024, description="From the answer `mfa_required`")
    code: OneTimeCode


class RefreshRequest(BaseModel):
    refresh_token: str = Field(max_length=256)


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: str
    display_name: str
    role: Literal["user", "admin"]
    created_at: datetime
    mfa_enabled: bool = Field(description="A second factor (TOTP) is set up")
    sso: bool = Field(description="Linked to an account at the single sign-on provider")
    has_password: bool = Field(description="False for accounts that only use single sign-on")


class AdminUserOut(UserOut):
    last_login_at: datetime | None
    must_change_password: bool


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
    auth_method: Literal["pwd", "mfa", "sso"]
    mfa_setup_required: bool = Field(
        description="Only the endpoints for setting up the second factor work until it is done"
    )
    password_change_required: bool = Field(
        description="Only /auth/password works until a new password is set"
    )


class MfaSetup(BaseModel):
    secret: str = Field(description="Base32 secret for typing it into the authenticator app")
    otpauth_uri: str = Field(description="The same as a link or QR code content")


class MfaEnabled(AuthResponse):
    recovery_codes: list[str] = Field(description="Shown once; each works one time")


class RecoveryCodes(BaseModel):
    recovery_codes: list[str]


class TemporaryPassword(BaseModel):
    temporary_password: str = Field(
        description="Shown once; the user has to choose a new password at the next sign-in"
    )


class OidcConfig(BaseModel):
    enabled: bool
    name: str


class OidcStart(BaseModel):
    authorization_url: str
    state: str


class OidcCallback(BaseModel):
    state: str = Field(max_length=256)
    code: str = Field(max_length=4096)


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
