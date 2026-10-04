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


def create_access_token(user_id: uuid.UUID, method: str = "pwd") -> tuple[str, int]:
    """Return a signed access token and its lifetime in seconds.

    `method` says how the user signed in: `pwd` (password only), `mfa` (password and
    one-time code) or `sso`.
    """
    settings = get_settings()
    lifetime = timedelta(minutes=settings.access_token_ttl_minutes)
    now = utcnow()
    payload = {
        "sub": str(user_id),
        "type": "access",
        "amr": method,
        "iat": now,
        "exp": now + lifetime,
    }
    token = jwt.encode(payload, settings.secret_key, algorithm=JWT_ALGORITHM)
    return token, int(lifetime.total_seconds())


def decode_access(token: str) -> tuple[uuid.UUID, str] | None:
    """Return user id and sign-in method of a valid access token, otherwise None."""
    try:
        payload = jwt.decode(
            token,
            get_settings().secret_key,
            algorithms=[JWT_ALGORITHM],
            options={"require": ["sub", "exp"]},
        )
        if payload.get("type") != "access":
            return None
        return uuid.UUID(payload["sub"]), str(payload.get("amr") or "pwd")
    except (jwt.InvalidTokenError, ValueError):
        return None


MFA_TOKEN_MINUTES = 5


def create_mfa_token(user_id: uuid.UUID) -> str:
    """Proof that the password was right, for the second step of the sign-in.

    It is not an access token: it only lets its holder try the one-time code, for a
    few minutes.
    """
    now = utcnow()
    payload = {
        "sub": str(user_id),
        "type": "mfa",
        "iat": now,
        "exp": now + timedelta(minutes=MFA_TOKEN_MINUTES),
    }
    return jwt.encode(payload, get_settings().secret_key, algorithm=JWT_ALGORITHM)


def decode_mfa_token(token: str) -> uuid.UUID | None:
    try:
        payload = jwt.decode(
            token,
            get_settings().secret_key,
            algorithms=[JWT_ALGORITHM],
            options={"require": ["sub", "exp"]},
        )
        if payload.get("type") != "mfa":
            return None
        return uuid.UUID(payload["sub"])
    except (jwt.InvalidTokenError, ValueError):
        return None


def decode_access_token(token: str) -> uuid.UUID | None:
    """Return the user id of a valid access token, otherwise None."""
    decoded = decode_access(token)
    return decoded[0] if decoded else None


def new_refresh_token() -> tuple[str, str]:
    """Return an opaque refresh token and the hash under which it is stored."""
    token = secrets.token_urlsafe(48)
    return token, hash_token(token)


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()
