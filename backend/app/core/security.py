import hashlib
import secrets
import uuid
from datetime import timedelta

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError

from app.core.config import get_settings
from app.core.db import utcnow

JWT_ALGORITHM = "HS256"

_hasher = PasswordHasher()
# Verified when the account does not exist, so that login timing does not reveal it.
_DUMMY_HASH = _hasher.hash(secrets.token_urlsafe(16))


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(password: str, password_hash: str | None) -> bool:
    try:
        _hasher.verify(password_hash or _DUMMY_HASH, password)
    except (VerificationError, InvalidHashError):
        return False
    return password_hash is not None


def create_access_token(user_id: uuid.UUID) -> tuple[str, int]:
    """Return a signed access token and its lifetime in seconds."""
    settings = get_settings()
    lifetime = timedelta(minutes=settings.access_token_ttl_minutes)
    now = utcnow()
    payload = {"sub": str(user_id), "type": "access", "iat": now, "exp": now + lifetime}
    token = jwt.encode(payload, settings.secret_key, algorithm=JWT_ALGORITHM)
    return token, int(lifetime.total_seconds())


def decode_access_token(token: str) -> uuid.UUID | None:
    """Return the user id of a valid access token, otherwise None."""
    try:
        payload = jwt.decode(
            token,
            get_settings().secret_key,
            algorithms=[JWT_ALGORITHM],
            options={"require": ["sub", "exp"]},
        )
        if payload.get("type") != "access":
            return None
        return uuid.UUID(payload["sub"])
    except (jwt.InvalidTokenError, ValueError):
        return None


def new_refresh_token() -> tuple[str, str]:
    """Return an opaque refresh token and the hash under which it is stored."""
    token = secrets.token_urlsafe(48)
    return token, hash_token(token)


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()
