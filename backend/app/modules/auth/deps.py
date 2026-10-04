from dataclasses import dataclass
from typing import Annotated

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core.config import get_settings
from app.core.deps import DbSession
from app.core.errors import ForbiddenError, UnauthorizedError
from app.core.security import decode_access
from app.modules.auth.models import METHOD_PASSWORD, ROLE_ADMIN, User

_bearer = HTTPBearer(auto_error=False)


@dataclass(frozen=True)
class UserSession:
    """Who is signed in and how (`pwd`, `mfa` or `sso`)."""

    user: User
    method: str


def get_session(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
    db: DbSession,
) -> UserSession:
    """The signed-in user without further conditions. Only for the endpoints that
    finish the sign-in: setting up the second factor and changing the password."""
    if credentials is None:
        raise UnauthorizedError("Not authenticated")
    decoded = decode_access(credentials.credentials)
    user = db.get(User, decoded[0]) if decoded else None
    if user is None:
        raise UnauthorizedError("Invalid or expired access token", code="invalid_token")
    return UserSession(user, decoded[1])


SignedIn = Annotated[UserSession, Depends(get_session)]


def mfa_setup_required(session: UserSession) -> bool:
    """A password alone is not enough where the second factor is mandatory."""
    return get_settings().mfa_required and session.method == METHOD_PASSWORD


def get_current_user(session: SignedIn) -> User:
    """The user for everything else: the sign-in must be complete."""
    if session.user.must_change_password:
        raise ForbiddenError("Choose a new password first", code="password_change_required")
    if mfa_setup_required(session):
        raise ForbiddenError("Set up the second factor first", code="mfa_setup_required")
    return session.user


CurrentUser = Annotated[User, Depends(get_current_user)]


def is_admin(user: User) -> bool:
    return user.role == ROLE_ADMIN


def require_admin(user: CurrentUser) -> User:
    if not is_admin(user):
        raise ForbiddenError("Admin role required")
    return user


AdminUser = Annotated[User, Depends(require_admin)]
