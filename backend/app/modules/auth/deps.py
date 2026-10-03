from typing import Annotated

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core.deps import DbSession
from app.core.errors import ForbiddenError, UnauthorizedError
from app.core.security import decode_access_token
from app.modules.auth.models import ROLE_ADMIN, User

_bearer = HTTPBearer(auto_error=False)


def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
    db: DbSession,
) -> User:
    if credentials is None:
        raise UnauthorizedError("Not authenticated")
    user_id = decode_access_token(credentials.credentials)
    user = db.get(User, user_id) if user_id else None
    if user is None:
        raise UnauthorizedError("Invalid or expired access token", code="invalid_token")
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


def require_admin(user: CurrentUser) -> User:
    if user.role != ROLE_ADMIN:
        raise ForbiddenError("Admin role required")
    return user


AdminUser = Annotated[User, Depends(require_admin)]
