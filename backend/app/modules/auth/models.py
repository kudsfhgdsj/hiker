import uuid
from datetime import datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Uuid,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base, UTCDateTime, utcnow

ROLE_USER = "user"
ROLE_ADMIN = "admin"
# How a session was started; kept in the tokens.
METHOD_PASSWORD = "pwd"
METHOD_MFA = "mfa"
METHOD_SSO = "sso"
# Stored instead of a hash for accounts that only sign in through single sign-on.
NO_PASSWORD = "!"


class User(Base):
    # "user" is a reserved word in PostgreSQL, hence the table name.
    __tablename__ = "user_account"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    email: Mapped[str] = mapped_column(String(320), unique=True)
    display_name: Mapped[str] = mapped_column(String(100))
    password_hash: Mapped[str] = mapped_column(String(255))
    role: Mapped[str] = mapped_column(String(16), default=ROLE_USER)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)
    last_login_at: Mapped[datetime | None] = mapped_column(UTCDateTime)
    # Set after an admin reset the password: the user has to choose a new one.
    must_change_password: Mapped[bool] = mapped_column(Boolean, default=False)
    # Second factor (TOTP). The pending secret waits for the first correct code.
    totp_secret: Mapped[str | None] = mapped_column(String(64))
    totp_pending_secret: Mapped[str | None] = mapped_column(String(64))
    totp_enabled_at: Mapped[datetime | None] = mapped_column(UTCDateTime)
    # Counter of the last accepted code: a code works only once.
    totp_last_counter: Mapped[int | None] = mapped_column(BigInteger)
    # Identity at the OpenID Connect provider, if the account is linked.
    oidc_issuer: Mapped[str | None] = mapped_column(String(255))
    oidc_subject: Mapped[str | None] = mapped_column(String(255))

    __table_args__ = (Index("ix_user_account_oidc", "oidc_issuer", "oidc_subject", unique=True),)

    @property
    def mfa_enabled(self) -> bool:
        return self.totp_enabled_at is not None

    @property
    def sso(self) -> bool:
        return self.oidc_subject is not None

    @property
    def has_password(self) -> bool:
        return self.password_hash != NO_PASSWORD


class UserProfile(Base):
    """Optional health data for the calorie estimate. Visible to its owner only."""

    __tablename__ = "user_profile"

    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("user_account.id", ondelete="CASCADE"), primary_key=True
    )
    weight_kg: Mapped[float | None] = mapped_column(Float)
    birth_year: Mapped[int | None] = mapped_column(Integer)
    sex: Mapped[str | None] = mapped_column(String(16))
    max_heart_rate: Mapped[int | None] = mapped_column(Integer)
    resting_heart_rate: Mapped[int | None] = mapped_column(Integer)
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)


class RefreshToken(Base):
    __tablename__ = "refresh_token"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("user_account.id", ondelete="CASCADE"), index=True
    )
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)
    expires_at: Mapped[datetime] = mapped_column(UTCDateTime)
    revoked_at: Mapped[datetime | None] = mapped_column(UTCDateTime)
    auth_method: Mapped[str] = mapped_column(String(8), default=METHOD_PASSWORD)


class RecoveryCode(Base):
    """One-time code that stands in for the authenticator app if it is lost."""

    __tablename__ = "recovery_code"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("user_account.id", ondelete="CASCADE"), index=True
    )
    code_hash: Mapped[str] = mapped_column(String(64))
    used_at: Mapped[datetime | None] = mapped_column(UTCDateTime)


class OidcLogin(Base):
    """A single sign-on that was started and waits for the answer of the provider."""

    __tablename__ = "oidc_login"

    state_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    nonce: Mapped[str] = mapped_column(String(128))
    code_verifier: Mapped[str] = mapped_column(String(128))
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)
