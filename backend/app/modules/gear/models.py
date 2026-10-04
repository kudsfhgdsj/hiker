import uuid
from datetime import date, datetime

from sqlalchemy import JSON, Column, Date, Float, ForeignKey, Integer, String, Table, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base, TimestampMixin, UTCDateTime, utcnow

STATUS_ACTIVE = "active"
STATUS_RETIRED = "retired"
TAG_FAVORITE = "favorite"
CURRENCY = "EUR"

CATALOG_PENDING = "pending"
CATALOG_APPROVED = "approved"
CATALOG_REJECTED = "rejected"


class GearType(Base):
    """Category of gear. Without an owner it belongs to the standard list for everyone."""

    __tablename__ = "gear_type"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("user_account.id", ondelete="CASCADE"), index=True
    )
    name: Mapped[str] = mapped_column(String(80))
    # Decides which extra attributes items of this type carry (see attributes.py).
    kind: Mapped[str | None] = mapped_column(String(32))
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow, onupdate=utcnow)


class GearCatalogItem(Base):
    """Shared catalog entry: product data only, never personal fields."""

    __tablename__ = "gear_catalog_item"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("user_account.id", ondelete="SET NULL")
    )
    name: Mapped[str] = mapped_column(String(200))
    brand: Mapped[str | None] = mapped_column(String(100))
    type_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("gear_type.id", ondelete="SET NULL")
    )
    nominal_weight_g: Mapped[int | None] = mapped_column(Integer)
    website_url: Mapped[str | None] = mapped_column(String(500))
    image_file_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("file_object.id", ondelete="SET NULL")
    )
    status: Mapped[str] = mapped_column(String(16), default=CATALOG_PENDING, index=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow, onupdate=utcnow)


class GearTag(Base):
    """Free label defined by a user to group gear in any way they like."""

    __tablename__ = "gear_tag"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("user_account.id", ondelete="CASCADE"), index=True
    )
    name: Mapped[str] = mapped_column(String(50))
    color: Mapped[str | None] = mapped_column(String(7))
    # Set for tags every user has and cannot delete, e.g. "favorite".
    system: Mapped[str | None] = mapped_column(String(32))
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow, onupdate=utcnow)


gear_item_tag = Table(
    "gear_item_tag",
    Base.metadata,
    Column("gear_item_id", Uuid, ForeignKey("gear_item.id", ondelete="CASCADE"), primary_key=True),
    Column(
        "tag_id", Uuid, ForeignKey("gear_tag.id", ondelete="CASCADE"), primary_key=True, index=True
    ),
)


class GearItem(TimestampMixin, Base):
    __tablename__ = "gear_item"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("user_account.id", ondelete="CASCADE"), index=True
    )
    catalog_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("gear_catalog_item.id", ondelete="SET NULL")
    )
    type_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("gear_type.id", ondelete="SET NULL")
    )
    name: Mapped[str] = mapped_column(String(200))
    brand: Mapped[str | None] = mapped_column(String(100))
    weight_g: Mapped[int | None] = mapped_column(Integer)
    purchase_date: Mapped[date | None] = mapped_column(Date)
    purchase_price: Mapped[float | None] = mapped_column(Float)
    currency: Mapped[str | None] = mapped_column(String(3))
    description: Mapped[str | None] = mapped_column(Text)
    notes: Mapped[str | None] = mapped_column(Text)
    website_url: Mapped[str | None] = mapped_column(String(500))
    image_file_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("file_object.id", ondelete="SET NULL")
    )
    status: Mapped[str] = mapped_column(String(16), default=STATUS_ACTIVE)
    serial_number: Mapped[str | None] = mapped_column(String(100))
    size: Mapped[str | None] = mapped_column(String(50))
    color: Mapped[str | None] = mapped_column(String(50))
    attributes: Mapped[dict | None] = mapped_column(JSON, default=dict)

    tags: Mapped[list[GearTag]] = relationship(
        secondary=gear_item_tag, lazy="selectin", order_by=GearTag.name
    )

    @property
    def tag_ids(self) -> list[uuid.UUID]:
        return [tag.id for tag in self.tags]

    @property
    def favorite(self) -> bool:
        return any(tag.system == TAG_FAVORITE for tag in self.tags)


class GearList(TimestampMixin, Base):
    """Packing list template."""

    __tablename__ = "gear_list"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("user_account.id", ondelete="CASCADE"), index=True
    )
    name: Mapped[str] = mapped_column(String(200))
    description: Mapped[str | None] = mapped_column(Text)

    entries: Mapped[list["GearListItem"]] = relationship(
        cascade="all, delete-orphan", lazy="selectin"
    )


class GearListItem(Base):
    __tablename__ = "gear_list_item"

    list_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("gear_list.id", ondelete="CASCADE"), primary_key=True
    )
    gear_item_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("gear_item.id", ondelete="CASCADE"), primary_key=True
    )
    quantity: Mapped[int] = mapped_column(Integer, default=1)
