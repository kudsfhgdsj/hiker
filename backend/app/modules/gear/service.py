"""Personal gear: types, items and packing lists."""

import uuid
from dataclasses import dataclass

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.core import files
from app.core.config import get_settings
from app.core.db import utcnow
from app.core.errors import ConflictError, ForbiddenError, UnprocessableError
from app.core.images import reencode_image
from app.core.storage import Storage
from app.modules.auth.deps import is_admin
from app.modules.auth.models import User
from app.modules.gear import attributes
from app.modules.gear.models import (
    CATALOG_APPROVED,
    CURRENCY,
    TAG_FAVORITE,
    GearCatalogItem,
    GearItem,
    GearList,
    GearListItem,
    GearTag,
    GearType,
)
from app.modules.gear.schemas import (
    GearItemCreate,
    GearItemIn,
    GearListCreate,
    GearListEntry,
    GearListIn,
    GearListOut,
    GearTagCreate,
    GearTagIn,
    GearTypeCreate,
    GearTypeIn,
)


def _contains(column, text: str):
    return func.lower(column).contains(text.lower(), autoescape=True)


# --- Types ---


def _visible_types(user: User):
    return or_(GearType.owner_id.is_(None), GearType.owner_id == user.id)


def list_types(db: Session, user: User) -> list[GearType]:
    query = select(GearType).where(_visible_types(user))
    return list(db.scalars(query.order_by(GearType.sort_order, GearType.name)))


def _check_type_name_is_free(db: Session, user: User, name: str, *, except_id=None) -> None:
    query = select(GearType.id).where(
        _visible_types(user), func.lower(GearType.name) == name.lower()
    )
    if except_id is not None:
        query = query.where(GearType.id != except_id)
    if db.scalar(query) is not None:
        raise ConflictError("A gear type with this name already exists", code="type_name_taken")


def create_type(db: Session, user: User, data: GearTypeCreate) -> GearType:
    if data.standard and not is_admin(user):
        raise ForbiddenError("Only an admin can change the standard list")
    _check_type_name_is_free(db, user, data.name)
    gear_type = GearType(
        owner_id=None if data.standard else user.id,
        name=data.name,
        sort_order=data.sort_order,
        kind=data.kind,
    )
    db.add(gear_type)
    db.commit()
    return gear_type


def update_type(db: Session, user: User, gear_type: GearType, data: GearTypeIn) -> GearType:
    _check_type_name_is_free(db, user, data.name, except_id=gear_type.id)
    gear_type.name = data.name
    gear_type.sort_order = data.sort_order
    gear_type.kind = data.kind
    db.commit()
    return gear_type


def delete_type(db: Session, gear_type: GearType) -> None:
    """Delete the type; items and catalog entries that used it lose their type."""
    db.delete(gear_type)
    db.commit()


def _usable_type(db: Session, user: User, type_id: uuid.UUID | None) -> GearType | None:
    if type_id is None:
        return None
    gear_type = db.scalar(select(GearType).where(GearType.id == type_id, _visible_types(user)))
    if gear_type is None:
        raise UnprocessableError("Unknown gear type", code="unknown_type")
    return gear_type


# --- Public interface for other modules ---


def get_item_for_user(db: Session, user: User, item_id: uuid.UUID) -> GearItem | None:
    """A gear item the user may use (their own, not deleted), otherwise None."""
    item = db.get(GearItem, item_id)
    if item is None or item.owner_id != user.id or item.deleted_at is not None:
        return None
    return item


def existing_item_ids(db: Session, item_ids) -> set[uuid.UUID]:
    """Those of the given ids that still refer to a gear item (deleted ones included)."""
    ids = {item_id for item_id in item_ids if item_id is not None}
    if not ids:
        return set()
    return set(db.scalars(select(GearItem.id).where(GearItem.id.in_(ids))))


# --- Tags ---


FAVORITE_NAME = "Favorit"
FAVORITE_COLOR = "#f5b400"


def favorite_tag(db: Session, user: User) -> GearTag:
    """The tag "favorite" every user has. It is created when it is first needed; a tag
    the user already named like it becomes the favourite tag."""
    owned = select(GearTag).where(GearTag.owner_id == user.id)
    tag = db.scalar(owned.where(GearTag.system == TAG_FAVORITE))
    if tag is None:
        tag = db.scalar(owned.where(func.lower(GearTag.name) == FAVORITE_NAME.lower()))
        if tag is None:
            tag = GearTag(owner_id=user.id, name=FAVORITE_NAME, color=FAVORITE_COLOR)
            db.add(tag)
        tag.system = TAG_FAVORITE
        db.commit()
    return tag


def list_tags(db: Session, user: User) -> list[GearTag]:
    favorite_tag(db, user)
    query = select(GearTag).where(GearTag.owner_id == user.id)
    # The favourite tag first, then by name.
    order = (GearTag.system.is_(None), func.lower(GearTag.name), GearTag.id)
    return list(db.scalars(query.order_by(*order)))


def _check_tag_name_is_free(db: Session, user: User, name: str, *, except_id=None) -> None:
    query = select(GearTag.id).where(
        GearTag.owner_id == user.id, func.lower(GearTag.name) == name.lower()
    )
    if except_id is not None:
        query = query.where(GearTag.id != except_id)
    if db.scalar(query) is not None:
        raise ConflictError("A tag with this name already exists", code="tag_name_taken")


def create_tag(db: Session, user: User, data: GearTagCreate) -> GearTag:
    if data.id is not None and db.get(GearTag, data.id) is not None:
        raise ConflictError("A tag with this id already exists", code="id_taken")
    _check_tag_name_is_free(db, user, data.name)
    tag = GearTag(owner_id=user.id, **data.model_dump(exclude_none=True))
    db.add(tag)
    db.commit()
    return tag


def _system_tag_error() -> ConflictError:
    return ConflictError("This tag belongs to the app and stays as it is", code="system_tag")


def update_tag(db: Session, user: User, tag: GearTag, data: GearTagIn) -> GearTag:
    if tag.system is not None and data.name != tag.name:
        raise _system_tag_error()
    _check_tag_name_is_free(db, user, data.name, except_id=tag.id)
    tag.name = data.name
    tag.color = data.color
    db.commit()
    return tag


def delete_tag(db: Session, tag: GearTag) -> None:
    """Delete the tag; the items that carried it stay."""
    if tag.system is not None:
        raise _system_tag_error()
    db.delete(tag)
    db.commit()


def _load_tags(db: Session, user: User, tag_ids: list[uuid.UUID]) -> list[GearTag]:
    ids = set(tag_ids)
    if not ids:
        return []
    tags = list(db.scalars(select(GearTag).where(GearTag.id.in_(ids), GearTag.owner_id == user.id)))
    if len(tags) != len(ids):
        raise UnprocessableError("Unknown tag", code="unknown_tag")
    return tags


# --- Items ---


@dataclass(frozen=True)
class ItemFilter:
    q: str | None = None
    type_id: uuid.UUID | None = None
    status: str | None = None
    tag_ids: tuple[uuid.UUID, ...] = ()
    favorite: bool | None = None


def item_conditions(user: User, filters: ItemFilter) -> list:
    conditions = [GearItem.owner_id == user.id, GearItem.deleted_at.is_(None)]
    if filters.q:
        q = filters.q
        conditions.append(or_(_contains(GearItem.name, q), _contains(GearItem.brand, q)))
    if filters.type_id is not None:
        conditions.append(GearItem.type_id == filters.type_id)
    if filters.status is not None:
        conditions.append(GearItem.status == filters.status)
    # Several tags narrow the result: an item must carry all of them.
    for tag_id in filters.tag_ids:
        conditions.append(GearItem.tags.any(GearTag.id == tag_id))
    if filters.favorite is not None:
        is_favorite = GearItem.tags.any(GearTag.system == TAG_FAVORITE)
        conditions.append(is_favorite if filters.favorite else ~is_favorite)
    return conditions


def list_items(
    db: Session, user: User, filters: ItemFilter, *, limit: int, offset: int
) -> tuple[list[GearItem], int]:
    conditions = item_conditions(user, filters)
    total = db.scalar(select(func.count()).select_from(GearItem).where(*conditions))
    query = select(GearItem).where(*conditions).order_by(func.lower(GearItem.name), GearItem.id)
    return list(db.scalars(query.limit(limit).offset(offset))), total


def create_item(db: Session, storage: Storage, user: User, data: GearItemCreate) -> GearItem:
    if data.id is not None and db.get(GearItem, data.id) is not None:
        raise ConflictError("A gear item with this id already exists", code="id_taken")
    gear_type = _usable_type(db, user, data.type_id)
    item = GearItem(
        owner_id=user.id,
        tags=_load_tags(db, user, data.tag_ids),
        attributes=attributes.clean(gear_type.kind if gear_type else None, data.attributes),
        currency=CURRENCY if data.purchase_price is not None else None,
        **data.model_dump(exclude_none=True, exclude={"tag_ids", "attributes"}),
    )
    if data.catalog_id is not None:
        template = db.get(GearCatalogItem, data.catalog_id)
        if template is None or template.status != CATALOG_APPROVED:
            raise UnprocessableError("Unknown catalog entry", code="unknown_catalog_item")
        # A copy, not a reference: later catalog changes do not touch the item.
        image = files.copy_file(db, storage, template.image_file_id, owner_id=user.id)
        item.image_file_id = image.id if image else None
    db.add(item)
    db.commit()
    return item


def update_item(db: Session, user: User, item: GearItem, data: GearItemIn) -> GearItem:
    gear_type = (
        _usable_type(db, user, data.type_id)
        if data.type_id != item.type_id
        else db.get(GearType, data.type_id)
        if data.type_id
        else None
    )
    for field, value in data.model_dump(exclude={"tag_ids", "attributes"}).items():
        setattr(item, field, value)
    item.attributes = attributes.clean(gear_type.kind if gear_type else None, data.attributes)
    item.currency = CURRENCY if data.purchase_price is not None else None
    item.tags = _load_tags(db, user, data.tag_ids)
    item.updated_at = utcnow()
    db.commit()
    return item


def set_favorite(db: Session, user: User, item: GearItem, favorite: bool) -> GearItem:
    """Put the favourite tag on the item or take it off."""
    tag = favorite_tag(db, user)
    if favorite != item.favorite:
        item.tags = [*item.tags, tag] if favorite else [t for t in item.tags if t.id != tag.id]
        item.updated_at = utcnow()
        db.commit()
    return item


def delete_item(db: Session, storage: Storage, item: GearItem) -> None:
    """Soft delete (the row stays for sync and tour history); the image is removed."""
    image_file_id = item.image_file_id
    item.image_file_id = None
    item.deleted_at = utcnow()
    db.commit()
    files.delete_file(db, storage, image_file_id)


def set_item_image(db: Session, storage: Storage, item: GearItem, data: bytes) -> GearItem:
    encoded, mime = reencode_image(data, max_edge=get_settings().image_max_edge_px)
    previous = item.image_file_id
    image = files.store_file(
        db, storage, owner_id=item.owner_id, data=encoded, mime=mime, extension="jpg"
    )
    item.image_file_id = image.id
    db.commit()
    files.delete_file(db, storage, previous)
    return item


def remove_item_image(db: Session, storage: Storage, item: GearItem) -> None:
    previous = item.image_file_id
    item.image_file_id = None
    db.commit()
    files.delete_file(db, storage, previous)


# --- Packing lists ---


def _check_entries(db: Session, user: User, entries: list[GearListEntry]) -> None:
    ids = [entry.gear_item_id for entry in entries]
    if len(set(ids)) != len(ids):
        raise UnprocessableError("A gear item appears more than once", code="duplicate_gear_item")
    if not ids:
        return
    owned = db.scalar(
        select(func.count())
        .select_from(GearItem)
        .where(GearItem.id.in_(ids), GearItem.owner_id == user.id, GearItem.deleted_at.is_(None))
    )
    if owned != len(ids):
        raise UnprocessableError("Unknown gear item in list", code="unknown_gear_item")


def _set_entries(gear_list: GearList, entries: list[GearListEntry]) -> None:
    gear_list.entries = [
        GearListItem(gear_item_id=entry.gear_item_id, quantity=entry.quantity) for entry in entries
    ]


def list_out(db: Session, gear_list: GearList) -> GearListOut:
    """Build the response; entries of deleted gear items are left out."""
    rows = db.execute(
        select(GearListItem, GearItem.weight_g)
        .join(GearItem, GearItem.id == GearListItem.gear_item_id)
        .where(GearListItem.list_id == gear_list.id, GearItem.deleted_at.is_(None))
        .order_by(func.lower(GearItem.name), GearItem.id)
    ).all()
    return GearListOut(
        id=gear_list.id,
        name=gear_list.name,
        description=gear_list.description,
        entries=[GearListEntry.model_validate(entry) for entry, _ in rows],
        total_weight_g=sum((weight or 0) * entry.quantity for entry, weight in rows),
        created_at=gear_list.created_at,
        updated_at=gear_list.updated_at,
    )


def list_lists(db: Session, user: User) -> list[GearList]:
    query = select(GearList).where(GearList.owner_id == user.id, GearList.deleted_at.is_(None))
    return list(db.scalars(query.order_by(func.lower(GearList.name), GearList.id)))


def create_list(db: Session, user: User, data: GearListCreate) -> GearList:
    if data.id is not None and db.get(GearList, data.id) is not None:
        raise ConflictError("A packing list with this id already exists", code="id_taken")
    _check_entries(db, user, data.entries)
    gear_list = GearList(owner_id=user.id, name=data.name, description=data.description)
    if data.id is not None:
        gear_list.id = data.id
    _set_entries(gear_list, data.entries)
    db.add(gear_list)
    db.commit()
    return gear_list


def update_list(db: Session, user: User, gear_list: GearList, data: GearListIn) -> GearList:
    _check_entries(db, user, data.entries)
    gear_list.name = data.name
    gear_list.description = data.description
    gear_list.updated_at = utcnow()
    gear_list.entries.clear()
    db.flush()
    _set_entries(gear_list, data.entries)
    db.commit()
    return gear_list


def delete_list(db: Session, gear_list: GearList) -> None:
    gear_list.deleted_at = utcnow()
    db.commit()
