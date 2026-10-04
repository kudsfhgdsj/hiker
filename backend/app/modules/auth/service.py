import logging
import math
import secrets
import string
import threading
import time
import uuid
from collections import deque
from dataclasses import dataclass
from datetime import timedelta

from sqlalchemy import delete, func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core import files
from app.core.config import get_settings
from app.core.db import utcnow
from app.core.errors import (
    AppError,
    ConflictError,
    ForbiddenError,
    NotFoundError,
    UnauthorizedError,
    UnprocessableError,
)
from app.core.ratelimit import RateLimitError
from app.core.security import (
    create_access_token,
    create_mfa_token,
    decode_mfa_token,
    hash_password,
    hash_token,
    new_refresh_token,
    verify_password,
)
from app.core.storage import Storage
from app.modules.auth import passwords, totp
from app.modules.auth.models import (
    METHOD_MFA,
    METHOD_PASSWORD,
    NO_PASSWORD,
    ROLE_ADMIN,
    ROLE_USER,
    OidcLogin,
    RecoveryCode,
    RefreshToken,
    User,
    UserProfile,
)
from app.modules.auth.oidc import OidcError, OidcProvider, challenge_of, new_verifier
from app.modules.auth.schemas import Profile

logger = logging.getLogger(__name__)

RECOVERY_CODE_COUNT = 10
OIDC_LOGIN_MINUTES = 10
TOTP_ISSUER = "hiker"


class OidcUnavailableError(AppError):
    status_code = 502
    code = "oidc_failed"


@dataclass(frozen=True)
class TokenPair:
    access_token: str
    refresh_token: str
    expires_in: int


def get_user_by_email(db: Session, email: str) -> User | None:
    return db.scalar(select(User).where(User.email == email.strip().lower()))


def get_display_names(db: Session, user_ids) -> dict:
    """Display names by user id, for other modules that show who owns or wrote something."""
    ids = set(user_ids)
    if not ids:
        return {}
    return dict(db.execute(select(User.id, User.display_name).where(User.id.in_(ids))).all())


def _is_first_user(db: Session) -> bool:
    return db.scalar(select(func.count()).select_from(User)) == 0


def register_user(db: Session, *, email: str, display_name: str, password: str) -> User:
    if get_settings().registration_mode != "open":
        raise ForbiddenError("Registration is closed", code="registration_closed")
    if get_user_by_email(db, email) is not None:
        raise ConflictError("E-mail address is already registered", code="email_taken")
    passwords.check_password(password, email=email, display_name=display_name)
    user = User(
        email=email,
        display_name=display_name,
        password_hash=hash_password(password),
        # The first registered user moderates the shared catalogs and manages the users.
        role=ROLE_ADMIN if _is_first_user(db) else ROLE_USER,
    )
    db.add(user)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise ConflictError("E-mail address is already registered", code="email_taken") from exc
    return user


# --- Second factor ---


def _hash_recovery_code(code: str) -> str:
    return hash_token("".join(code.lower().split()))


def _use_code(db: Session, user: User, code: str) -> bool:
    """Accept a code of the authenticator app or an unused recovery code, once."""
    if user.totp_secret:
        counter = totp.verify(user.totp_secret, code, user.totp_last_counter)
        if counter is not None:
            user.totp_last_counter = counter
            return True
    recovery = db.scalar(
        select(RecoveryCode).where(
            RecoveryCode.user_id == user.id,
            RecoveryCode.code_hash == _hash_recovery_code(code),
            RecoveryCode.used_at.is_(None),
        )
    )
    if recovery is None:
        return False
    recovery.used_at = utcnow()
    return True


def _new_recovery_codes(db: Session, user: User) -> list[str]:
    db.execute(delete(RecoveryCode).where(RecoveryCode.user_id == user.id))
    codes = []
    for _ in range(RECOVERY_CODE_COUNT):
        raw = secrets.token_hex(5)
        code = f"{raw[:5]}-{raw[5:]}"
        codes.append(code)
        db.add(RecoveryCode(user_id=user.id, code_hash=_hash_recovery_code(code)))
    return codes


def mfa_setup(db: Session, user: User) -> tuple[str, str]:
    """Start setting up the second factor: a new secret that waits for its first code."""
    user.totp_pending_secret = totp.new_secret()
    db.commit()
    uri = totp.provisioning_uri(user.totp_pending_secret, user.email, TOTP_ISSUER)
    return user.totp_pending_secret, uri


def mfa_enable(db: Session, user: User, code: str) -> list[str]:
    """Confirm the pending secret with a code; returns the recovery codes."""
    counter = (
        totp.verify(user.totp_pending_secret, code, None) if user.totp_pending_secret else None
    )
    if counter is None:
        raise UnprocessableError("The code is not correct", code="invalid_mfa_code")
    user.totp_secret = user.totp_pending_secret
    user.totp_pending_secret = None
    user.totp_enabled_at = utcnow()
    user.totp_last_counter = counter
    codes = _new_recovery_codes(db, user)
    # Sessions that were started without the second factor end here.
    _revoke_all(db, user.id)
    db.commit()
    return codes


def _check_totp(db: Session, user: User, code: str) -> None:
    counter = (
        totp.verify(user.totp_secret, code, user.totp_last_counter) if user.totp_secret else None
    )
    if counter is None:
        raise UnprocessableError("The code is not correct", code="invalid_mfa_code")
    user.totp_last_counter = counter


def regenerate_recovery_codes(db: Session, user: User, code: str) -> list[str]:
    _check_totp(db, user, code)
    codes = _new_recovery_codes(db, user)
    db.commit()
    return codes


def _clear_mfa(db: Session, user: User) -> None:
    user.totp_secret = None
    user.totp_pending_secret = None
    user.totp_enabled_at = None
    user.totp_last_counter = None
    db.execute(delete(RecoveryCode).where(RecoveryCode.user_id == user.id))


def mfa_disable(db: Session, user: User, code: str) -> None:
    if get_settings().mfa_required:
        raise ForbiddenError("The second factor is mandatory on this server", code="mfa_mandatory")
    _check_totp(db, user, code)
    _clear_mfa(db, user)
    db.commit()


# --- Sign-in ---


def login(db: Session, *, email: str, password: str, code: str | None) -> tuple[User, str]:
    """Check the credentials; returns the user and how they signed in."""
    user = get_user_by_email(db, email)
    usable_hash = user.password_hash if user is not None and user.has_password else None
    if not verify_password(password, usable_hash):
        raise UnauthorizedError("Wrong e-mail address or password", code="invalid_credentials")
    method = METHOD_PASSWORD
    if user.mfa_enabled:
        if not code:
            # The password was right: the client asks for the code in a second step
            # and sends it together with this token.
            error = UnauthorizedError(
                "The code of the second factor is needed", code="mfa_required"
            )
            error.extra = {"mfa_token": create_mfa_token(user.id)}
            raise error
        _check_second_factor(db, user, code)
        method = METHOD_MFA
    user.last_login_at = utcnow()
    db.commit()
    return user, method


# Wrong codes per account before it has to wait; guessing six digits must not pay off.
MFA_ATTEMPTS = 5
MFA_ATTEMPT_WINDOW_SECONDS = 600
_mfa_failures: dict[uuid.UUID, deque[float]] = {}
_mfa_lock = threading.Lock()


def _check_second_factor(db: Session, user: User, code: str) -> None:
    now = time.monotonic()
    with _mfa_lock:
        failures = _mfa_failures.setdefault(user.id, deque())
        while failures and failures[0] <= now - MFA_ATTEMPT_WINDOW_SECONDS:
            failures.popleft()
        if len(failures) >= MFA_ATTEMPTS:
            wait = math.ceil(failures[0] + MFA_ATTEMPT_WINDOW_SECONDS - now)
            raise RateLimitError(wait)
    if not _use_code(db, user, code):
        db.rollback()
        with _mfa_lock:
            _mfa_failures.setdefault(user.id, deque()).append(now)
        raise UnauthorizedError("The code is not correct", code="invalid_mfa_code")
    with _mfa_lock:
        _mfa_failures.pop(user.id, None)


def reset_mfa_attempts() -> None:
    with _mfa_lock:
        _mfa_failures.clear()


def login_second_step(db: Session, *, mfa_token: str, code: str) -> tuple[User, str]:
    """Finish a sign-in that was answered with `mfa_required`."""
    user_id = decode_mfa_token(mfa_token)
    user = db.get(User, user_id) if user_id else None
    if user is None or not user.mfa_enabled:
        raise UnauthorizedError("This sign-in has expired, start again", code="mfa_token_invalid")
    _check_second_factor(db, user, code)
    user.last_login_at = utcnow()
    db.commit()
    return user, METHOD_MFA


def issue_tokens(db: Session, user: User, method: str = METHOD_PASSWORD) -> TokenPair:
    access_token, expires_in = create_access_token(user.id, method)
    refresh_token, token_hash = new_refresh_token()
    lifetime = timedelta(days=get_settings().refresh_token_ttl_days)
    db.add(
        RefreshToken(
            user_id=user.id,
            token_hash=token_hash,
            expires_at=utcnow() + lifetime,
            auth_method=method,
        )
    )
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
    return user, issue_tokens(db, user, row.auth_method)


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


def change_password(db: Session, user: User, *, current: str, new: str, method: str) -> TokenPair:
    """Set a new password; all other sessions end."""
    if not user.has_password or not verify_password(current, user.password_hash):
        raise UnprocessableError("The current password is not correct", code="wrong_password")
    if new == current:
        raise UnprocessableError("Choose a password you did not use before", code="weak_password")
    passwords.check_password(new, email=user.email, display_name=user.display_name)
    user.password_hash = hash_password(new)
    user.must_change_password = False
    _revoke_all(db, user.id)
    return issue_tokens(db, user, method)


# --- Administration of users ---


def list_users(db: Session) -> list[User]:
    return list(db.scalars(select(User).order_by(func.lower(User.email))))


def get_user(db: Session, user_id) -> User:
    user = db.get(User, user_id)
    if user is None:
        raise NotFoundError("User not found")
    return user


def delete_user(db: Session, storage: Storage, admin: User, target: User) -> None:
    """Remove an account with everything it owns.

    Tours, gear and foods of the user go with the account (foreign keys), their files
    are removed from the storage. What the user proposed to the shared catalogs stays,
    and so does the history of tours of others, without the name of the author.
    """
    if target.id == admin.id:
        raise ConflictError("You cannot remove your own account", code="cannot_delete_self")
    files.delete_files_of_owner(db, storage, target.id)
    db.delete(target)
    db.commit()


def _temporary_password() -> str:
    """A random password that follows the rules; the user replaces it at once."""
    alphabets = (string.ascii_lowercase, string.ascii_uppercase, string.digits, "-_+!")
    characters = [secrets.choice(alphabet) for alphabet in alphabets]
    everything = "".join(alphabets[:3])
    characters += [secrets.choice(everything) for _ in range(12)]
    secrets.SystemRandom().shuffle(characters)
    return "".join(characters)


def reset_password(db: Session, target: User) -> str:
    password = _temporary_password()
    target.password_hash = hash_password(password)
    target.must_change_password = True
    _revoke_all(db, target.id)
    db.commit()
    return password


def reset_mfa(db: Session, target: User) -> None:
    """Remove the second factor, e.g. after a lost phone; it is set up again at the next login."""
    _clear_mfa(db, target)
    _revoke_all(db, target.id)
    db.commit()


# --- Single sign-on ---


def oidc_redirect_uri() -> str:
    return f"{get_settings().public_base_url}/login/sso/callback"


def oidc_start(db: Session, provider: OidcProvider) -> tuple[str, str]:
    """Begin a sign-in at the provider; returns the address to send the browser to."""
    db.execute(
        delete(OidcLogin).where(
            OidcLogin.created_at < utcnow() - timedelta(minutes=OIDC_LOGIN_MINUTES)
        )
    )
    state, nonce, verifier = secrets.token_urlsafe(32), secrets.token_urlsafe(32), new_verifier()
    db.add(OidcLogin(state_hash=hash_token(state), nonce=nonce, code_verifier=verifier))
    db.commit()
    try:
        url = provider.authorization_url(
            state=state,
            nonce=nonce,
            challenge=challenge_of(verifier),
            redirect_uri=oidc_redirect_uri(),
        )
    except OidcError as exc:
        raise OidcUnavailableError(str(exc)) from exc
    return url, state


def oidc_finish(db: Session, provider: OidcProvider, *, state: str, code: str) -> User:
    """Finish the sign-in: find, link or create the account of the person."""
    started = db.get(OidcLogin, hash_token(state))
    expired = utcnow() - timedelta(minutes=OIDC_LOGIN_MINUTES)
    if started is None or started.created_at < expired:
        raise UnauthorizedError("This sign-in has expired, start again", code="oidc_state_invalid")
    nonce, verifier = started.nonce, started.code_verifier
    # The state works once, whatever the provider answers.
    db.delete(started)
    db.commit()
    try:
        identity = provider.exchange(
            code=code, verifier=verifier, nonce=nonce, redirect_uri=oidc_redirect_uri()
        )
    except OidcError as exc:
        logger.warning("OIDC sign-in failed: %s", exc)
        raise OidcUnavailableError("The sign-in at the provider failed") from exc
    user = db.scalar(
        select(User).where(
            User.oidc_issuer == identity.issuer, User.oidc_subject == identity.subject
        )
    )
    if user is None:
        confirmed = identity.email_verified or not get_settings().oidc_require_verified_email
        if identity.email is None or not confirmed:
            raise ForbiddenError(
                "The provider did not confirm an e-mail address", code="oidc_email_unverified"
            )
        user = get_user_by_email(db, identity.email)
        if user is None:
            # The provider decides who may sign in, whatever REGISTRATION_MODE says.
            name = (identity.name or identity.email.split("@")[0]).strip()[:100] or "?"
            user = User(
                email=identity.email,
                display_name=name,
                password_hash=NO_PASSWORD,
                role=ROLE_ADMIN if _is_first_user(db) else ROLE_USER,
            )
            db.add(user)
        user.oidc_issuer = identity.issuer
        user.oidc_subject = identity.subject
    user.last_login_at = utcnow()
    db.commit()
    return user


def get_profile(db: Session, user: User) -> UserProfile | None:
    return db.get(UserProfile, user.id)


def get_profile_by_user_id(db: Session, user_id) -> UserProfile | None:
    """Profile of a user for calculations in other modules. Health data: never expose it."""
    return db.get(UserProfile, user_id)


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
