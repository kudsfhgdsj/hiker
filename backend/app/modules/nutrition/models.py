import uuid
from datetime import datetime

from sqlalchemy import Float, ForeignKey, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base, TimestampMixin, UTCDateTime

SOURCE_CUSTOM = "custom"
SOURCE_OPENFOODFACTS = "openfoodfacts"

PRIVATE = "private"
CATALOG_PENDING = "catalog_pending"
CATALOG_REJECTED = "catalog_rejected"
CATALOG = "catalog"


class FoodItem(TimestampMixin, Base):
    """A food with nutrition values per 100 g.

    Private foods and proposals belong to a user. Entries of the shared catalog
    (visibility `catalog`) have no owner.
    """

    __tablename__ = "food_item"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("user_account.id", ondelete="CASCADE"), index=True
    )
    # Private food: the catalog entry it was copied from or proposed as.
    catalog_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("food_item.id", ondelete="SET NULL")
    )
    # Catalog entry or proposal: the user who proposed it.
    proposed_by: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("user_account.id", ondelete="SET NULL")
    )
    barcode: Mapped[str | None] = mapped_column(String(14), index=True)
    name: Mapped[str] = mapped_column(String(200))
    brand: Mapped[str | None] = mapped_column(String(100))
    kcal_per_100g: Mapped[float | None] = mapped_column(Float)
    protein_g: Mapped[float | None] = mapped_column(Float)
    carbs_g: Mapped[float | None] = mapped_column(Float)
    fat_g: Mapped[float | None] = mapped_column(Float)
    sugar_g: Mapped[float | None] = mapped_column(Float)
    salt_g: Mapped[float | None] = mapped_column(Float)
    serving_size_g: Mapped[float | None] = mapped_column(Float)
    image_url: Mapped[str | None] = mapped_column(String(500))
    source: Mapped[str] = mapped_column(String(16), default=SOURCE_CUSTOM)
    source_synced_at: Mapped[datetime | None] = mapped_column(UTCDateTime)
    visibility: Mapped[str] = mapped_column(String(20), default=PRIVATE, index=True)


NUTRIENT_FIELDS = (
    "kcal_per_100g",
    "protein_g",
    "carbs_g",
    "fat_g",
    "sugar_g",
    "salt_g",
    "serving_size_g",
)
