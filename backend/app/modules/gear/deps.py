"""Central access checks of the gear module: every record is loaded through these."""

import uuid
from typing import Annotated

from fastapi import Depends

from app.core.deps import DbSession
from app.core.errors import ForbiddenError, NotFoundError
from app.modules.auth.deps import CurrentUser, is_admin
from app.modules.gear.models import (
    CATALOG_APPROVED,
    GearCatalogItem,
    GearItem,
    GearList,
    GearTag,
    GearType,
)


def get_owned_item(item_id: uuid.UUID, user: CurrentUser, db: DbSession) -> GearItem:
    item = db.get(GearItem, item_id)
    # Foreign items answer like missing ones, so that ids cannot be probed.
    if item is None or item.owner_id != user.id or item.deleted_at is not None:
        raise NotFoundError("Gear item not found")
    return item


def get_owned_list(list_id: uuid.UUID, user: CurrentUser, db: DbSession) -> GearList:
    gear_list = db.get(GearList, list_id)
    if gear_list is None or gear_list.owner_id != user.id or gear_list.deleted_at is not None:
        raise NotFoundError("Packing list not found")
    return gear_list


def get_owned_tag(tag_id: uuid.UUID, user: CurrentUser, db: DbSession) -> GearTag:
    tag = db.get(GearTag, tag_id)
    if tag is None or tag.owner_id != user.id:
        raise NotFoundError("Tag not found")
    return tag


def get_editable_type(type_id: uuid.UUID, user: CurrentUser, db: DbSession) -> GearType:
    gear_type = db.get(GearType, type_id)
    if gear_type is None or gear_type.owner_id not in (None, user.id):
        raise NotFoundError("Gear type not found")
    if gear_type.owner_id is None and not is_admin(user):
        raise ForbiddenError("Only an admin can change the standard list")
    return gear_type


def get_readable_catalog_item(
    catalog_id: uuid.UUID, user: CurrentUser, db: DbSession
) -> GearCatalogItem:
    """Approved entries are visible to every user, others to the proposer and admins."""
    entry = db.get(GearCatalogItem, catalog_id)
    if entry is None or not (
        entry.status == CATALOG_APPROVED or entry.created_by == user.id or is_admin(user)
    ):
        raise NotFoundError("Catalog entry not found")
    return entry


OwnedItem = Annotated[GearItem, Depends(get_owned_item)]
OwnedList = Annotated[GearList, Depends(get_owned_list)]
OwnedTag = Annotated[GearTag, Depends(get_owned_tag)]
EditableType = Annotated[GearType, Depends(get_editable_type)]
ReadableCatalogItem = Annotated[GearCatalogItem, Depends(get_readable_catalog_item)]
