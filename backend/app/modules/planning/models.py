import uuid
from datetime import date

from sqlalchemy import JSON, Boolean, Date, Float, ForeignKey, Integer, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base, TimestampMixin

PROFILE_HIKING = "hiking"
PROFILE_DIRECT = "direct"
PROFILES = (PROFILE_HIKING, PROFILE_DIRECT)

# SAC hiking scale T1 … T6 and the values of the OpenStreetMap key `sac_scale`.
SAC_SCALE = (
    "hiking",
    "mountain_hiking",
    "demanding_mountain_hiking",
    "alpine_hiking",
    "demanding_alpine_hiking",
    "difficult_alpine_hiking",
)


class PlannedRoute(TimestampMixin, Base):
    """A route planned ahead: waypoints set by the user and the line computed from them."""

    __tablename__ = "planned_route"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("user_account.id", ondelete="CASCADE"), index=True
    )
    title: Mapped[str] = mapped_column(String(200))
    description: Mapped[str | None] = mapped_column(Text)
    planned_date: Mapped[date | None] = mapped_column(Date)
    profile: Mapped[str] = mapped_column(String(20), default=PROFILE_HIKING)
    # Hardest allowed path, 1 (T1) to 6 (T6), and whether via ferratas may be used.
    max_difficulty: Mapped[int] = mapped_column(Integer, default=3)
    via_ferrata: Mapped[bool] = mapped_column(Boolean, default=False)
    # What the user set: [{"lat", "lon", "name", "direct"}, ...]
    waypoints: Mapped[list] = mapped_column(JSON)
    # The computed line, as columns of equal length like the series of a track.
    series: Mapped[dict] = mapped_column(JSON)
    # Which engine computed the line: "brouter", "direct" or both ("brouter+direct").
    engine: Mapped[str] = mapped_column(String(30))
    distance_m: Mapped[float] = mapped_column(Float)
    ascent_m: Mapped[float | None] = mapped_column(Float)
    descent_m: Mapped[float | None] = mapped_column(Float)
    min_elevation_m: Mapped[float | None] = mapped_column(Float)
    max_elevation_m: Mapped[float | None] = mapped_column(Float)
    # Estimated walking time without breaks (see estimate.py).
    duration_s: Mapped[int] = mapped_column(Integer)
    version: Mapped[int] = mapped_column(Integer, default=0)

    # Optimistic locking: an UPDATE only succeeds if the version is still the one we read.
    __mapper_args__ = {"version_id_col": version, "version_id_generator": False}
