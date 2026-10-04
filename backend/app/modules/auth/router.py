import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query, status

from app.core.config import get_settings
from app.core.deps import DbSession, FileStorage
from app.core.errors import ForbiddenError, NotFoundError, error_responses
from app.core.ratelimit import rate_limit
from app.modules.auth import service
from app.modules.auth.deps import AdminUser, CurrentUser, SignedIn, mfa_setup_required
from app.modules.auth.models import METHOD_MFA, METHOD_PASSWORD, METHOD_SSO
from app.modules.auth.oidc import Oidc
from app.modules.auth.schemas import (
    AdminUserOut,
    AuthResponse,
    CodeRequest,
    Email,
    LoginRequest,
    MfaEnabled,
    MfaSetup,
    OidcCallback,
    OidcConfig,
    OidcStart,
    PasswordChange,
    Profile,
    RecoveryCodes,
    RefreshRequest,
    RegisterRequest,
    TemporaryPassword,
    TokenResponse,
    UserLookupOut,
    UserOut,
)

router = APIRouter()

# Slows down password guessing and mass registration.
auth_rate_limit = Depends(rate_limit("auth", limit=20))


def _auth_fields(user, tokens: service.TokenPair, method: str) -> dict:
    return {
        "access_token": tokens.access_token,
        "refresh_token": tokens.refresh_token,
        "expires_in": tokens.expires_in,
        "user": UserOut.model_validate(user),
        "auth_method": method,
        "mfa_setup_required": get_settings().mfa_required and method == METHOD_PASSWORD,
        "password_change_required": user.must_change_password,
    }


def _auth_response(user, tokens: service.TokenPair, method: str) -> AuthResponse:
    return AuthResponse(**_auth_fields(user, tokens, method))


@router.post(
    "/auth/register",
    dependencies=[auth_rate_limit],
    response_model=AuthResponse,
    status_code=status.HTTP_201_CREATED,
    tags=["auth"],
    responses=error_responses(403, 409),
)
def register(body: RegisterRequest, db: DbSession):
    """Create an account. The password must follow the rules (422 `weak_password`).

    Where the second factor is mandatory, the tokens only allow setting it up
    (`mfa_setup_required`).
    """
    user = service.register_user(
        db, email=body.email, display_name=body.display_name, password=body.password
    )
    return _auth_response(user, service.issue_tokens(db, user), METHOD_PASSWORD)


@router.post(
    "/auth/login",
    dependencies=[auth_rate_limit],
    response_model=AuthResponse,
    tags=["auth"],
    responses=error_responses(401),
)
def login(body: LoginRequest, db: DbSession):
    """Sign in with e-mail and password.

    With a second factor set up, the code is needed too: without it the answer is
    401 `mfa_required`, with a wrong one 401 `invalid_mfa_code`. A recovery code works
    in place of the code, once.
    """
    user, method = service.login(db, email=body.email, password=body.password, code=body.code)
    return _auth_response(user, service.issue_tokens(db, user, method), method)


@router.post(
    "/auth/refresh",
    dependencies=[auth_rate_limit],
    response_model=TokenResponse,
    tags=["auth"],
    responses=error_responses(401),
)
def refresh(body: RefreshRequest, db: DbSession):
    """Exchange the refresh token. The old one becomes invalid (rotation)."""
    _user, tokens = service.rotate_refresh_token(db, body.refresh_token)
    return TokenResponse(
        access_token=tokens.access_token,
        refresh_token=tokens.refresh_token,
        expires_in=tokens.expires_in,
    )


@router.post("/auth/logout", status_code=status.HTTP_204_NO_CONTENT, tags=["auth"])
def logout(body: RefreshRequest, db: DbSession):
    service.revoke_refresh_token(db, body.refresh_token)


@router.post(
    "/auth/password",
    dependencies=[auth_rate_limit],
    response_model=AuthResponse,
    tags=["auth"],
    responses=error_responses(401),
)
def change_password(body: PasswordChange, session: SignedIn, db: DbSession):
    """Set a new password. All other sessions end; the answer carries new tokens."""
    tokens = service.change_password(
        db,
        session.user,
        current=body.current_password,
        new=body.new_password,
        method=session.method,
    )
    return _auth_response(session.user, tokens, session.method)


# --- Second factor (TOTP) ---


@router.post(
    "/auth/mfa/setup",
    dependencies=[auth_rate_limit],
    response_model=MfaSetup,
    tags=["mfa"],
    responses=error_responses(401, 403),
)
def mfa_setup(session: SignedIn, db: DbSession):
    """Start (or restart) the setup: a new secret for the authenticator app.

    The current second factor stays valid until the new secret is confirmed. Replacing
    an existing second factor needs a session that used it.
    """
    if session.user.mfa_enabled and session.method == METHOD_PASSWORD:
        raise ForbiddenError("Sign in with the second factor first", code="mfa_required")
    secret, uri = service.mfa_setup(db, session.user)
    return MfaSetup(secret=secret, otpauth_uri=uri)


@router.post(
    "/auth/mfa/enable",
    dependencies=[auth_rate_limit],
    response_model=MfaEnabled,
    tags=["mfa"],
    responses=error_responses(401),
)
def mfa_enable(body: CodeRequest, session: SignedIn, db: DbSession):
    """Confirm the setup with a code of the app. Returns new tokens and the recovery codes."""
    if session.user.mfa_enabled and session.method == METHOD_PASSWORD:
        raise ForbiddenError("Sign in with the second factor first", code="mfa_required")
    codes = service.mfa_enable(db, session.user, body.code)
    method = METHOD_SSO if session.method == METHOD_SSO else METHOD_MFA
    tokens = service.issue_tokens(db, session.user, method)
    return MfaEnabled(**_auth_fields(session.user, tokens, method), recovery_codes=codes)


@router.post(
    "/auth/mfa/recovery-codes",
    dependencies=[auth_rate_limit],
    response_model=RecoveryCodes,
    tags=["mfa"],
    responses=error_responses(401, 403),
)
def new_recovery_codes(body: CodeRequest, user: CurrentUser, db: DbSession):
    """Replace the recovery codes; needs a current code of the app."""
    return RecoveryCodes(recovery_codes=service.regenerate_recovery_codes(db, user, body.code))


@router.post(
    "/auth/mfa/disable",
    dependencies=[auth_rate_limit],
    status_code=status.HTTP_204_NO_CONTENT,
    tags=["mfa"],
    responses=error_responses(401, 403),
)
def mfa_disable(body: CodeRequest, user: CurrentUser, db: DbSession):
    """Remove the second factor. Not possible where it is mandatory (`MFA_REQUIRED`)."""
    service.mfa_disable(db, user, body.code)


# --- Single sign-on (OpenID Connect) ---


@router.get("/auth/oidc", response_model=OidcConfig, tags=["sso"])
def oidc_config(provider: Oidc):
    """Whether single sign-on is offered, and under which name."""
    return OidcConfig(enabled=provider is not None, name=get_settings().oidc_name)


@router.post(
    "/auth/oidc/start",
    dependencies=[auth_rate_limit],
    response_model=OidcStart,
    tags=["sso"],
    responses=error_responses(404, 502),
)
def oidc_start(provider: Oidc, db: DbSession):
    """Begin a sign-in: the client sends the browser to `authorization_url`.

    The provider answers to `<PUBLIC_BASE_URL>/login/sso/callback`.
    """
    if provider is None:
        raise NotFoundError("Single sign-on is not configured")
    url, state = service.oidc_start(db, provider)
    return OidcStart(authorization_url=url, state=state)


@router.post(
    "/auth/oidc/callback",
    dependencies=[auth_rate_limit],
    response_model=AuthResponse,
    tags=["sso"],
    responses=error_responses(401, 403, 404, 502),
)
def oidc_callback(body: OidcCallback, provider: Oidc, db: DbSession):
    """Finish the sign-in with what the provider sent back (`state` and `code`).

    An account with the same confirmed e-mail address is linked, otherwise a new one
    is created. The second factor is the business of the provider here.
    """
    if provider is None:
        raise NotFoundError("Single sign-on is not configured")
    user = service.oidc_finish(db, provider, state=body.state, code=body.code)
    return _auth_response(user, service.issue_tokens(db, user, METHOD_SSO), METHOD_SSO)


# --- Users ---


@router.get(
    "/users/lookup",
    response_model=UserLookupOut,
    tags=["users"],
    responses=error_responses(401, 404),
)
def lookup_user(email: Annotated[Email, Query()], _user: CurrentUser, db: DbSession):
    """Find a user by exact e-mail address, for sharing and tour partners."""
    found = service.get_user_by_email(db, email)
    if found is None:
        raise NotFoundError("No user with this e-mail address")
    return found


@router.get("/me", response_model=UserOut, tags=["me"], responses=error_responses(401))
def read_me(session: SignedIn):
    """The own account; also works while the sign-in is not complete yet."""
    return session.user


@router.get("/me/session", tags=["me"], responses=error_responses(401))
def read_session(session: SignedIn) -> dict:
    """What is still missing before the session can be used."""
    return {
        "auth_method": session.method,
        "mfa_setup_required": mfa_setup_required(session),
        "password_change_required": session.user.must_change_password,
    }


@router.get("/me/profile", response_model=Profile, tags=["me"], responses=error_responses(401))
def read_profile(user: CurrentUser, db: DbSession):
    return service.get_profile(db, user) or Profile()


@router.put("/me/profile", response_model=Profile, tags=["me"], responses=error_responses(401))
def write_profile(body: Profile, user: CurrentUser, db: DbSession):
    return service.save_profile(db, user, body)


# --- Administration ---

admin_responses = error_responses(401, 403, 404)


@router.get(
    "/admin/users", response_model=list[AdminUserOut], tags=["admin"], responses=admin_responses
)
def list_users(_admin: AdminUser, db: DbSession):
    """All accounts, for the administrator."""
    return service.list_users(db)


@router.delete(
    "/admin/users/{user_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    tags=["admin"],
    responses={**admin_responses, **error_responses(409)},
)
def delete_user(user_id: uuid.UUID, admin: AdminUser, db: DbSession, storage: FileStorage):
    """Remove an account with its tours, gear, foods and files. Not the own account."""
    service.delete_user(db, storage, admin, service.get_user(db, user_id))


@router.post(
    "/admin/users/{user_id}/reset-password",
    response_model=TemporaryPassword,
    tags=["admin"],
    responses=admin_responses,
)
def reset_password(user_id: uuid.UUID, _admin: AdminUser, db: DbSession):
    """Give the account a temporary password. It is shown once; the user has to choose
    a new one at the next sign-in. All sessions of the user end."""
    password = service.reset_password(db, service.get_user(db, user_id))
    return TemporaryPassword(temporary_password=password)


@router.post(
    "/admin/users/{user_id}/reset-mfa",
    status_code=status.HTTP_204_NO_CONTENT,
    tags=["admin"],
    responses=admin_responses,
)
def reset_mfa(user_id: uuid.UUID, _admin: AdminUser, db: DbSession):
    """Remove the second factor of an account, e.g. after a lost phone."""
    service.reset_mfa(db, service.get_user(db, user_id))
