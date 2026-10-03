"""Offline sync of the gear module."""

from datetime import datetime

from sqlalchemy import select

from app.core.errors import NotFoundError
from app.core.sync import SyncChanges, SyncConflictError, SyncContext, SyncOperation, SyncSource
from app.modules.gear import service
from app.modules.gear.models import GearItem, GearTag
from app.modules.gear.schemas import GearItemCreate, GearItemIn, GearItemOut, GearTagOut


def _item_json(item: GearItem) -> dict:
    return GearItemOut.model_validate(item).model_dump(mode="json")


def _item_changes(context: SyncContext, since: datetime | None) -> SyncChanges:
    query = select(GearItem).where(GearItem.owner_id == context.user.id)
    if since is not None:
        query = query.where(GearItem.updated_at > since)
    items = list(context.db.scalars(query))
    return SyncChanges(
        changed=[_item_json(item) for item in items if item.deleted_at is None],
        # Without `since` the client starts empty and needs no tombstones.
        deleted=[item.id for item in items if item.deleted_at is not None and since is not None],
    )


def _push_item(context: SyncContext, operation: SyncOperation) -> dict | None:
    db, user = context.db, context.user
    item = db.get(GearItem, operation.id)
    usable = item is not None and item.owner_id == user.id and item.deleted_at is None
    if operation.op == "delete":
        if usable:
            service.delete_item(db, context.storage, item)
        return None
    if item is None:
        data = GearItemCreate.model_validate({**(operation.data or {}), "id": operation.id})
        return _item_json(service.create_item(db, context.storage, user, data))
    if not usable:
        raise NotFoundError("Gear item not found")
    if operation.base_updated_at is not None and item.updated_at != operation.base_updated_at:
        raise SyncConflictError(_item_json(item))
    data = GearItemIn.model_validate(operation.data or {})
    return _item_json(service.update_item(db, user, item, data))


def _types(context: SyncContext, _since: datetime | None) -> SyncChanges:
    types = service.list_types(context.db, context.user)
    changed = [
        {
            "id": str(t.id),
            "name": t.name,
            "sort_order": t.sort_order,
            "standard": t.owner_id is None,
        }
        for t in types
    ]
    return SyncChanges(changed=changed, full=True)


def _tags(context: SyncContext, _since: datetime | None) -> SyncChanges:
    tags: list[GearTag] = service.list_tags(context.db, context.user)
    changed = [GearTagOut.model_validate(tag).model_dump(mode="json") for tag in tags]
    return SyncChanges(changed=changed, full=True)


def _lists(context: SyncContext, _since: datetime | None) -> SyncChanges:
    lists = service.list_lists(context.db, context.user)
    changed = [service.list_out(context.db, item).model_dump(mode="json") for item in lists]
    return SyncChanges(changed=changed, full=True)


# Types, tags and packing lists are small: they are always sent as a whole.
SOURCES = [
    SyncSource("gear_items", _item_changes, _push_item),
    SyncSource("gear_types", _types),
    SyncSource("gear_tags", _tags),
    SyncSource("gear_lists", _lists),
]
