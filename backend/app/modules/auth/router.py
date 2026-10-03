from typing import Annotated

from fastapi import APIRouter, Query, status

from app.core.deps import DbSession
from app.core.errors import NotFoundError, error_responses
from app.modules.auth import service
from app.modules.auth.deps import CurrentUser
from app.modules.auth.schemas import (
    AuthResponse,
    Email,
    LoginRequest,
    Profile,
    RefreshRequest,
    RegisterRequest,
    TokenResponse,
    UserLookupOut,
    UserOut,
)

router = APIRouter()


def _auth_response(user, tokens: service.TokenPair) -> AuthResponse:
    return AuthResponse(
        access_token=tokens.access_token,
        refresh_token=tokens.refresh_token,
        expires_in=tokens.expires_in,
        user=UserOut.model_validate(user),
    )


@router.post(
    "/auth/register",
    response_model=AuthResponse,
    status_code=status.HTTP_201_CREATED,
    tags=["auth"],
    responses=error_responses(403, 409),
)
def register(body: RegisterRequest, db: DbSession):
    user = service.register_user(
        db, email=body.email, display_name=body.display_name, password=body.password
    )
    return _auth_response(user, service.issue_tokens(db, user))


@router.post(
    "/auth/login", response_model=AuthResponse, tags=["auth"], responses=error_responses(401)
)
def login(body: LoginRequest, db: DbSession):
    user = service.authenticate(db, email=body.email, password=body.password)
    return _auth_response(user, service.issue_tokens(db, user))


@router.post(
    "/auth/refresh", response_model=TokenResponse, tags=["auth"], responses=error_responses(401)
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
def read_me(user: CurrentUser):
    return user


@router.get("/me/profile", response_model=Profile, tags=["me"], responses=error_responses(401))
def read_profile(user: CurrentUser, db: DbSession):
    return service.get_profile(db, user) or Profile()


@router.put("/me/profile", response_model=Profile, tags=["me"], responses=error_responses(401))
def write_profile(body: Profile, user: CurrentUser, db: DbSession):
    return service.save_profile(db, user, body)
