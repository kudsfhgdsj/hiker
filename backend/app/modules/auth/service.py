from dataclasses import dataclass
from datetime import timedelta

from sqlalchemy import func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.db import utcnow
from app.core.errors import ConflictError, ForbiddenError, UnauthorizedError
from app.core.security import (
    create_access_token,
    hash_password,
    hash_token,
    new_refresh_token,
    verify_password,
)
from app.modules.auth.models import ROLE_ADMIN, ROLE_USER, RefreshToken, User, UserProfile
from app.modules.auth.schemas import Profile


@dataclass(frozen=True)
class TokenPair:
    access_token: str
    refresh_token: str
    expires_in: int


def get_user_by_email(db: Session, email: str) -> User | None:
    return db.scalar(select(User).where(User.email == email.strip().lower()))


def register_user(db: Session, *, email: str, display_name: str, password: str) -> User:
    if get_settings().registration_mode != "open":
        raise ForbiddenError("Registration is closed", code="registration_closed")
    if get_user_by_email(db, email) is not None:
        raise ConflictError("E-mail address is already registered", code="email_taken")
    # The first registered user moderates the shared catalogs.
    is_first = db.scalar(select(func.count()).select_from(User)) == 0
    user = User(
        email=email,
        display_name=display_name,
        password_hash=hash_password(password),
        role=ROLE_ADMIN if is_first else ROLE_USER,
    )
    db.add(user)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise ConflictError("E-mail address is already registered", code="email_taken") from exc
    return user


def authenticate(db: Session, *, email: str, password: str) -> User:
    user = get_user_by_email(db, email)
    if not verify_password(password, user.password_hash if user else None):
        raise UnauthorizedError("Wrong e-mail address or password", code="invalid_credentials")
    return user


def issue_tokens(db: Session, user: User) -> TokenPair:
    access_token, expires_in = create_access_token(user.id)
    refresh_token, token_hash = new_refresh_token()
    lifetime = timedelta(days=get_settings().refresh_token_ttl_days)
    db.add(RefreshToken(user_id=user.id, token_hash=token_hash, expires_at=utcnow() + lifetime))
    db.commit()
    return TokenPair(access_token, refresh_token, expires_in)


def _revoke_all(db: Session, user_id) -> None:
    db.execute(
        update(RefreshToken)
        .where(RefreshToken.user_id == user_id, RefreshToken.revoked_at.is_(None))
        .values(revoked_at=utcnow())
    )


def rotate_refresh_token(db: Session, refresh_token: str) -> tuple[User, TokenPair]:
    """Exchange a refresh token for a new pair; every token is valid exactly once."""
    invalid = UnauthorizedError("Invalid refresh token", code="invalid_refresh_token")
    row = db.scalar(
        select(RefreshToken)
        .where(RefreshToken.token_hash == hash_token(refresh_token))
        .with_for_update()
    )
    if row is None:
        raise invalid
    if row.revoked_at is not None:
        # A used token shows up again: it may have been stolen, so end all sessions.
        _revoke_all(db, row.user_id)
        db.commit()
        raise invalid
    if row.expires_at <= utcnow():
        raise invalid
    user = db.get(User, row.user_id)
    row.revoked_at = utcnow()
    return user, issue_tokens(db, user)


def revoke_refresh_token(db: Session, refresh_token: str) -> None:
    db.execute(
        update(RefreshToken)
        .where(
            RefreshToken.token_hash == hash_token(refresh_token),
            RefreshToken.revoked_at.is_(None),
        )
        .values(revoked_at=utcnow())
    )
    db.commit()


def get_profile(db: Session, user: User) -> UserProfile | None:
    return db.get(UserProfile, user.id)


def save_profile(db: Session, user: User, data: Profile) -> UserProfile:
    profile = db.get(UserProfile, user.id)
    if profile is None:
        profile = UserProfile(user_id=user.id)
        db.add(profile)
    for field, value in data.model_dump().items():
        setattr(profile, field, value)
    profile.updated_at = utcnow()
    db.commit()
    return profile
