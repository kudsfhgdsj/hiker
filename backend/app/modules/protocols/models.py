import uuid
from datetime import datetime

from sqlalchemy import (
    JSON,
    Boolean,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    Uuid,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base, TimestampMixin, UTCDateTime, utcnow

PERMISSION_READ = "read"
PERMISSION_EDIT = "edit"

CALORIES_MANUAL = "manual"
CALORIES_ESTIMATED = "estimated"

TRACK_NONE = "none"


def _id_column() -> Mapped[uuid.UUID]:
    return mapped_column(Uuid, primary_key=True, default=uuid.uuid4)


def _tour_id_column() -> Mapped[uuid.UUID]:
    return mapped_column(Uuid, ForeignKey("tour.id", ondelete="CASCADE"), index=True)


def _user_reference() -> Mapped[uuid.UUID | None]:
    return mapped_column(Uuid, ForeignKey("user_account.id", ondelete="SET NULL"))


class TourGear(Base):
    """Gear taken on a tour. Name and weight are a snapshot of the gear item."""

    __tablename__ = "tour_gear"
    __table_args__ = (UniqueConstraint("tour_id", "gear_item_id"),)

    id: Mapped[uuid.UUID] = _id_column()
    tour_id: Mapped[uuid.UUID] = _tour_id_column()
    gear_item_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("gear_item.id", ondelete="SET NULL")
    )
    added_by: Mapped[uuid.UUID | None] = _user_reference()
    name_snapshot: Mapped[str] = mapped_column(String(200))
    brand_snapshot: Mapped[str | None] = mapped_column(String(100))
    weight_g_snapshot: Mapped[int | None] = mapped_column(Integer)
    quantity: Mapped[int] = mapped_column(Integer, default=1)
    carried: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)


class TourFoodEntry(Base):
    """Food on a tour. Name and calories are a snapshot of the food item."""

    __tablename__ = "tour_food_entry"

    id: Mapped[uuid.UUID] = _id_column()
    tour_id: Mapped[uuid.UUID] = _tour_id_column()
    food_item_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("food_item.id", ondelete="SET NULL")
    )
    added_by: Mapped[uuid.UUID | None] = _user_reference()
    name_snapshot: Mapped[str] = mapped_column(String(200))
    kcal_per_100g_snapshot: Mapped[float | None] = mapped_column(Float)
    amount_g: Mapped[float] = mapped_column(Float)
    kcal_snapshot: Mapped[float | None] = mapped_column(Float)
    # carried: counts towards the pack weight; eaten: counts towards the calories eaten.
    carried: Mapped[bool] = mapped_column(Boolean, default=True)
    eaten: Mapped[bool] = mapped_column(Boolean, default=False)
    eaten_at: Mapped[datetime | None] = mapped_column(UTCDateTime)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)


class TourPeak(Base):
    __tablename__ = "tour_peak"

    id: Mapped[uuid.UUID] = _id_column()
    tour_id: Mapped[uuid.UUID] = _tour_id_column()
    name: Mapped[str] = mapped_column(String(200))
    elevation_m: Mapped[int | None] = mapped_column(Integer)
    lat: Mapped[float | None] = mapped_column(Float)
    lon: Mapped[float | None] = mapped_column(Float)
    reached_at: Mapped[datetime | None] = mapped_column(UTCDateTime)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)


class TourWaypoint(Base):
    __tablename__ = "tour_waypoint"

    id: Mapped[uuid.UUID] = _id_column()
    tour_id: Mapped[uuid.UUID] = _tour_id_column()
    name: Mapped[str] = mapped_column(String(200))
    description: Mapped[str | None] = mapped_column(Text)
    icon: Mapped[str | None] = mapped_column(String(50))
    lat: Mapped[float] = mapped_column(Float)
    lon: Mapped[float] = mapped_column(Float)
    track_distance_m: Mapped[float | None] = mapped_column(Float)
    elevation_m: Mapped[float | None] = mapped_column(Float)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)


class Contact(TimestampMixin, Base):
    """A tour partner of a user: a placeholder name, optionally linked to a real user."""

    __tablename__ = "contact"

    id: Mapped[uuid.UUID] = _id_column()
    owner_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("user_account.id", ondelete="CASCADE"), index=True
    )
    display_name: Mapped[str] = mapped_column(String(100))
    linked_user_id: Mapped[uuid.UUID | None] = _user_reference()


class TourPartner(Base):
    __tablename__ = "tour_partner"

    tour_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("tour.id", ondelete="CASCADE"), primary_key=True
    )
    contact_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("contact.id", ondelete="CASCADE"), primary_key=True, index=True
    )
    added_by: Mapped[uuid.UUID | None] = _user_reference()

    contact: Mapped[Contact] = relationship(lazy="joined")


class TourShare(Base):
    __tablename__ = "tour_share"

    tour_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("tour.id", ondelete="CASCADE"), primary_key=True
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("user_account.id", ondelete="CASCADE"), primary_key=True, index=True
    )
    permission: Mapped[str] = mapped_column(String(8))
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)


class TourPhoto(Base):
    __tablename__ = "tour_photo"

    id: Mapped[uuid.UUID] = _id_column()
    tour_id: Mapped[uuid.UUID] = _tour_id_column()
    file_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("file_object.id", ondelete="SET NULL")
    )
    thumb_file_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("file_object.id", ondelete="SET NULL")
    )
    added_by: Mapped[uuid.UUID | None] = _user_reference()
    caption: Mapped[str | None] = mapped_column(String(500))
    taken_at: Mapped[datetime | None] = mapped_column(UTCDateTime)
    # Position as read from the image; kept so that the automatic position can come back.
    exif_lat: Mapped[float | None] = mapped_column(Float)
    exif_lon: Mapped[float | None] = mapped_column(Float)
    exif_altitude: Mapped[float | None] = mapped_column(Float)
    lat: Mapped[float | None] = mapped_column(Float)
    lon: Mapped[float | None] = mapped_column(Float)
    position_source: Mapped[str] = mapped_column(String(10), default="none")
    track_distance_m: Mapped[float | None] = mapped_column(Float)
    elevation_m: Mapped[float | None] = mapped_column(Float)
    waypoint_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("tour_waypoint.id", ondelete="SET NULL")
    )
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)


class TrackSeries(Base):
    """Thinned-out series of the track for the map and the charts, as columns of equal length."""

    __tablename__ = "track_series"

    tour_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("tour.id", ondelete="CASCADE"), primary_key=True
    )
    point_count: Mapped[int] = mapped_column(Integer)
    data: Mapped[dict] = mapped_column(JSON)


class TourPublicLink(Base):
    """Read-only access to a tour for anyone who knows the token."""

    __tablename__ = "tour_public_link"

    id: Mapped[uuid.UUID] = _id_column()
    tour_id: Mapped[uuid.UUID] = _tour_id_column()
    # Random UUIDv4 (os.urandom); the only secret of the link. Never log it.
    token: Mapped[uuid.UUID] = mapped_column(Uuid, unique=True, default=uuid.uuid4)
    created_by: Mapped[uuid.UUID | None] = _user_reference()
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)
    expires_at: Mapped[datetime | None] = mapped_column(UTCDateTime)
    revoked_at: Mapped[datetime | None] = mapped_column(UTCDateTime)
    hide_exact_start: Mapped[bool] = mapped_column(Boolean, default=False)
    strip_photo_gps: Mapped[bool] = mapped_column(Boolean, default=False)
    show_health_data: Mapped[bool] = mapped_column(Boolean, default=False)


class TourRevision(Base):
    """One entry of the change history. Rows are only ever inserted."""

    __tablename__ = "tour_revision"
    __table_args__ = (UniqueConstraint("tour_id", "version"),)

    id: Mapped[uuid.UUID] = _id_column()
    tour_id: Mapped[uuid.UUID] = _tour_id_column()
    version: Mapped[int] = mapped_column(Integer)
    # Emptied when the user is removed, which anonymises the history.
    author_user_id: Mapped[uuid.UUID | None] = _user_reference()
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)
    kind: Mapped[str] = mapped_column(String(10))
    change_summary: Mapped[str] = mapped_column(String(500))
    snapshot: Mapped[dict] = mapped_column(JSON)
    diff: Mapped[dict] = mapped_column(JSON)


class Tour(TimestampMixin, Base):
    __tablename__ = "tour"

    id: Mapped[uuid.UUID] = _id_column()
    owner_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("user_account.id", ondelete="CASCADE"), index=True
    )
    title: Mapped[str] = mapped_column(String(200))
    summary: Mapped[str | None] = mapped_column(Text)
    start_time: Mapped[datetime | None] = mapped_column(UTCDateTime)
    end_time: Mapped[datetime | None] = mapped_column(UTCDateTime)
    # Manual overrides; empty means "use the computed value".
    duration_minutes: Mapped[int | None] = mapped_column(Integer)
    pack_weight_start_g: Mapped[int | None] = mapped_column(Integer)
    calories_burned: Mapped[float | None] = mapped_column(Float)
    calories_burned_source: Mapped[str | None] = mapped_column(String(10))
    start_lat: Mapped[float | None] = mapped_column(Float)
    start_lon: Mapped[float | None] = mapped_column(Float)
    start_name: Mapped[str | None] = mapped_column(String(200))
    end_lat: Mapped[float | None] = mapped_column(Float)
    end_lon: Mapped[float | None] = mapped_column(Float)
    end_name: Mapped[str | None] = mapped_column(String(200))
    points_source: Mapped[str | None] = mapped_column(String(8))
    gpx_file_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("file_object.id", ondelete="SET NULL")
    )
    track_source: Mapped[str] = mapped_column(String(8), default=TRACK_NONE)
    track_stats: Mapped[dict | None] = mapped_column(JSON)
    cover_photo_id: Mapped[uuid.UUID | None] = mapped_column(Uuid)
    # Added to the capture time of photos before they are matched to the track by time.
    photo_time_offset_seconds: Mapped[int] = mapped_column(Integer, default=0)
    # Revision counter; raised by history.record_change on every change.
    version: Mapped[int] = mapped_column(Integer, default=0)

    # Optimistic locking: an UPDATE only succeeds if the version is still the one we read.
    __mapper_args__ = {"version_id_col": version, "version_id_generator": False}

    gear: Mapped[list[TourGear]] = relationship(
        cascade="all, delete-orphan", order_by=(TourGear.name_snapshot, TourGear.id)
    )
    food: Mapped[list[TourFoodEntry]] = relationship(
        cascade="all, delete-orphan", order_by=(TourFoodEntry.sort_order, TourFoodEntry.id)
    )
    peaks: Mapped[list[TourPeak]] = relationship(
        cascade="all, delete-orphan", order_by=(TourPeak.sort_order, TourPeak.id)
    )
    partners: Mapped[list[TourPartner]] = relationship(cascade="all, delete-orphan")
    photos: Mapped[list[TourPhoto]] = relationship(
        cascade="all, delete-orphan", order_by=(TourPhoto.sort_order, TourPhoto.id)
    )
    waypoints: Mapped[list[TourWaypoint]] = relationship(
        cascade="all, delete-orphan", order_by=(TourWaypoint.created_at, TourWaypoint.id)
    )
