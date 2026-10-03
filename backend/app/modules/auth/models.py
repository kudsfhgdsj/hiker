import uuid
from datetime import datetime

from sqlalchemy import Float, ForeignKey, Integer, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base, UTCDateTime, utcnow

ROLE_USER = "user"
ROLE_ADMIN = "admin"


class User(Base):
    # "user" is a reserved word in PostgreSQL, hence the table name.
    __tablename__ = "user_account"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    email: Mapped[str] = mapped_column(String(320), unique=True)
    display_name: Mapped[str] = mapped_column(String(100))
    password_hash: Mapped[str] = mapped_column(String(255))
    role: Mapped[str] = mapped_column(String(16), default=ROLE_USER)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)


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
