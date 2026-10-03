import logging
import uuid
from dataclasses import asdict
from datetime import timedelta

from pydantic import ValidationError
from sqlalchemy import and_, func, or_, select
from sqlalchemy.orm import Session, aliased

from app.core.config import get_settings
from app.core.db import utcnow
from app.core.errors import AppError, ConflictError, NotFoundError, UnprocessableError
from app.modules.auth.models import User
from app.modules.nutrition.models import (
    CATALOG,
    CATALOG_PENDING,
    CATALOG_REJECTED,
    PRIVATE,
    SOURCE_CUSTOM,
    SOURCE_OPENFOODFACTS,
    FoodItem,
)
from app.modules.nutrition.schemas import CatalogFoodPatch, FoodCreate, FoodIn
from app.modules.nutrition.sources import FoodData, FoodSource, FoodSourceError

logger = logging.getLogger(__name__)

COPIED_FIELDS = (
    "barcode",
    "name",
    "brand",
    "kcal_per_100g",
    "protein_g",
    "carbs_g",
    "fat_g",
    "sugar_g",
    "salt_g",
    "serving_size_g",
    "image_url",
)


class SourceUnavailableError(AppError):
    status_code = 502
    code = "source_unavailable"


def _contains(column, text: str):
    return func.lower(column).contains(text.lower(), autoescape=True)


def _matches(q: str | None) -> list:
    if not q:
        return []
    return [or_(_contains(FoodItem.name, q), _contains(FoodItem.brand, q), FoodItem.barcode == q)]


def _is_own(user: User):
    return and_(
        FoodItem.owner_id == user.id, FoodItem.visibility == PRIVATE, FoodItem.deleted_at.is_(None)
    )


def _in_catalog():
    return and_(FoodItem.visibility == CATALOG, FoodItem.deleted_at.is_(None))


def _page(db: Session, conditions: list, order_by: tuple, limit: int, offset: int):
    total = db.scalar(select(func.count()).select_from(FoodItem).where(*conditions))
    query = select(FoodItem).where(*conditions).order_by(*order_by)
    return list(db.scalars(query.limit(limit).offset(offset))), total


_BY_NAME = (func.lower(FoodItem.name), FoodItem.id)


# --- Own foods ---


def list_foods(db: Session, user: User, *, q: str | None, limit: int, offset: int):
    return _page(db, [_is_own(user), *_matches(q)], _BY_NAME, limit, offset)


def search(db: Session, user: User, *, q: str | None, limit: int, offset: int):
    """Own foods first, then the catalog without entries the user has a private copy of."""
    own_copy = aliased(FoodItem)
    has_own_copy = (
        select(own_copy.id)
        .where(
            own_copy.catalog_id == FoodItem.id,
            own_copy.owner_id == user.id,
            own_copy.visibility == PRIVATE,
            own_copy.deleted_at.is_(None),
        )
        .exists()
    )
    conditions = [or_(_is_own(user), and_(_in_catalog(), ~has_own_copy)), *_matches(q)]
    return _page(db, conditions, (FoodItem.visibility != PRIVATE, *_BY_NAME), limit, offset)


def _get_catalog_entry(db: Session, catalog_id: uuid.UUID | None) -> FoodItem | None:
    if catalog_id is None:
        return None
    return db.scalar(select(FoodItem).where(FoodItem.id == catalog_id, _in_catalog()))


def create_food(db: Session, user: User, data: FoodCreate) -> FoodItem:
    if data.id is not None and db.get(FoodItem, data.id) is not None:
        raise ConflictError("A food with this id already exists", code="id_taken")
    food = FoodItem(owner_id=user.id, visibility=PRIVATE, source=SOURCE_CUSTOM)
    if data.id is not None:
        food.id = data.id
    for field, value in data.model_dump(exclude={"id", "catalog_id"}).items():
        setattr(food, field, value)
    if data.catalog_id is not None:
        template = _get_catalog_entry(db, data.catalog_id)
        if template is None:
            raise UnprocessableError("Unknown catalog entry", code="unknown_catalog_item")
        # A copy, not a reference: later catalog changes do not touch the private food.
        food.catalog_id = template.id
        food.image_url = template.image_url
    db.add(food)
    db.commit()
    return food


def update_food(db: Session, food: FoodItem, data: FoodIn) -> FoodItem:
    for field, value in data.model_dump().items():
        setattr(food, field, value)
    db.commit()
    return food


def delete_food(db: Session, food: FoodItem) -> None:
    """Soft delete: the row stays for sync and for tours that reference it."""
    food.deleted_at = utcnow()
    db.commit()


# --- Barcode ---


def _apply_source_data(food: FoodItem, data: FoodData) -> None:
    for field, value in asdict(data).items():
        setattr(food, field, value)
    food.source = SOURCE_OPENFOODFACTS
    food.source_synced_at = utcnow()


def _is_stale(food: FoodItem) -> bool:
    if food.source != SOURCE_OPENFOODFACTS or food.source_synced_at is None:
        return False
    max_age = timedelta(days=get_settings().openfoodfacts_cache_days)
    return utcnow() - food.source_synced_at > max_age


def lookup_barcode(db: Session, user: User, source: FoodSource, barcode: str) -> FoodItem:
    """Own food, then the shared catalog (the cache of Open Food Facts), then the source."""
    newest_first = (FoodItem.updated_at.desc(), FoodItem.id)
    own = db.scalar(
        select(FoodItem).where(_is_own(user), FoodItem.barcode == barcode).order_by(*newest_first)
    )
    if own is not None:
        return own
    cached = db.scalar(
        select(FoodItem).where(_in_catalog(), FoodItem.barcode == barcode).order_by(*newest_first)
    )
    if cached is not None and not _is_stale(cached):
        return cached
    try:
        data = source.fetch_by_barcode(barcode)
    except FoodSourceError as exc:
        logger.warning("Food source lookup failed: %s", exc)
        if cached is not None:
            return cached
        raise SourceUnavailableError("The product database cannot be reached") from exc
    if data is None:
        if cached is not None:
            return cached
        raise NotFoundError("No product with this barcode", code="product_not_found")
    food = cached or FoodItem(owner_id=None, visibility=CATALOG)
    _apply_source_data(food, data)
    db.add(food)
    db.commit()
    return food


# --- Catalog ---


def list_pending(db: Session, *, limit: int, offset: int):
    conditions = [FoodItem.visibility == CATALOG_PENDING, FoodItem.deleted_at.is_(None)]
    return _page(db, conditions, (FoodItem.created_at, FoodItem.id), limit, offset)


def list_own_proposals(db: Session, user: User, *, limit: int, offset: int):
    """Everything the user proposed, whatever its status, newest first."""
    conditions = [FoodItem.proposed_by == user.id, FoodItem.deleted_at.is_(None)]
    return _page(db, conditions, (FoodItem.created_at.desc(), FoodItem.id), limit, offset)


def propose(db: Session, user: User, food: FoodItem) -> FoodItem:
    """Copy a private food into a pending catalog proposal."""
    linked = db.get(FoodItem, food.catalog_id) if food.catalog_id else None
    if linked is not None and linked.visibility != CATALOG_REJECTED:
        raise ConflictError(
            "This food is already linked to a catalog entry", code="already_in_catalog"
        )
    # The proposal stays with its proposer until an admin approves it.
    proposal = FoodItem(
        owner_id=user.id, proposed_by=user.id, visibility=CATALOG_PENDING, source=SOURCE_CUSTOM
    )
    for field in COPIED_FIELDS:
        setattr(proposal, field, getattr(food, field))
    db.add(proposal)
    db.flush()
    food.catalog_id = proposal.id
    db.commit()
    return proposal


def get_proposal(db: Session, catalog_id: uuid.UUID) -> FoodItem:
    entry = db.get(FoodItem, catalog_id)
    if entry is None or entry.visibility == PRIVATE or entry.deleted_at is not None:
        raise NotFoundError("Catalog entry not found")
    return entry


def moderate(db: Session, entry: FoodItem, data: CatalogFoodPatch) -> FoodItem:
    changes = data.model_dump(exclude_unset=True)
    visibility = changes.pop("visibility", None) or entry.visibility
    if changes:
        merged = {field: getattr(entry, field) for field in FoodIn.model_fields} | changes
        try:
            checked = FoodIn.model_validate(merged)
        except ValidationError as exc:
            message = "; ".join(error["msg"] for error in exc.errors())
            raise UnprocessableError(message, code="invalid_food") from exc
        for field in changes:
            setattr(entry, field, getattr(checked, field))
    if visibility == CATALOG and entry.barcode:
        duplicate = db.scalar(
            select(FoodItem.id).where(
                _in_catalog(), FoodItem.barcode == entry.barcode, FoodItem.id != entry.id
            )
        )
        if duplicate is not None:
            raise ConflictError(
                "The catalog already has a product with this barcode", code="barcode_in_catalog"
            )
    entry.visibility = visibility
    # Catalog entries belong to everyone; anything else stays with the proposer.
    entry.owner_id = None if visibility == CATALOG else entry.proposed_by
    db.commit()
    return entry
