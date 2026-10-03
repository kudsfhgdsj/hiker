"""Shared gear catalog: proposals by users, moderation by admins.

Only product data is shared. Personal fields of an item (purchase price and
date, notes, description, serial number, size, colour, status) never reach it.
"""

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.core import files
from app.core.errors import ConflictError, UnprocessableError
from app.core.storage import Storage
from app.modules.auth.models import User
from app.modules.gear.models import (
    CATALOG_APPROVED,
    CATALOG_PENDING,
    CATALOG_REJECTED,
    GearCatalogItem,
    GearItem,
    GearType,
)
from app.modules.gear.schemas import CatalogItemPatch


def _standard_type_id(db: Session, type_id):
    """Catalog entries only use the standard list; personal types are dropped."""
    if type_id is None:
        return None
    return db.scalar(select(GearType.id).where(GearType.id == type_id, GearType.owner_id.is_(None)))


def _page(db: Session, conditions, order_by, limit: int, offset: int):
    total = db.scalar(select(func.count()).select_from(GearCatalogItem).where(*conditions))
    query = select(GearCatalogItem).where(*conditions).order_by(*order_by)
    return list(db.scalars(query.limit(limit).offset(offset))), total


def search(db: Session, *, q: str | None, limit: int, offset: int):
    conditions = [GearCatalogItem.status == CATALOG_APPROVED]
    if q:
        pattern = q.lower()
        conditions.append(
            or_(
                func.lower(GearCatalogItem.name).contains(pattern, autoescape=True),
                func.lower(GearCatalogItem.brand).contains(pattern, autoescape=True),
            )
        )
    order_by = (func.lower(GearCatalogItem.name), GearCatalogItem.id)
    return _page(db, conditions, order_by, limit, offset)


def list_pending(db: Session, *, limit: int, offset: int):
    conditions = [GearCatalogItem.status == CATALOG_PENDING]
    return _page(db, conditions, (GearCatalogItem.created_at, GearCatalogItem.id), limit, offset)


def propose(db: Session, storage: Storage, user: User, item: GearItem) -> GearCatalogItem:
    """Copy the product data of an item into a pending catalog entry."""
    linked = db.get(GearCatalogItem, item.catalog_id) if item.catalog_id else None
    if linked is not None and linked.status != CATALOG_REJECTED:
        raise ConflictError(
            "This item is already linked to a catalog entry", code="already_in_catalog"
        )
    image = files.copy_file(db, storage, item.image_file_id, owner_id=user.id)
    entry = GearCatalogItem(
        created_by=user.id,
        name=item.name,
        brand=item.brand,
        type_id=_standard_type_id(db, item.type_id),
        nominal_weight_g=item.weight_g,
        website_url=item.website_url,
        image_file_id=image.id if image else None,
        status=CATALOG_PENDING,
    )
    db.add(entry)
    db.flush()
    item.catalog_id = entry.id
    db.commit()
    return entry


def moderate(db: Session, entry: GearCatalogItem, data: CatalogItemPatch) -> GearCatalogItem:
    changes = data.model_dump(exclude_unset=True)
    if changes.get("status", "") is None or changes.get("name", "") is None:
        raise UnprocessableError("status and name cannot be empty")
    if changes.get("type_id") is not None and _standard_type_id(db, changes["type_id"]) is None:
        raise UnprocessableError(
            "Catalog entries can only use standard gear types", code="unknown_type"
        )
    for field, value in changes.items():
        setattr(entry, field, value)
    db.commit()
    return entry
