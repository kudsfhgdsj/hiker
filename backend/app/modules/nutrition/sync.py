"""Offline sync of the nutrition module: the user's own foods."""

from datetime import datetime

from sqlalchemy import select

from app.core.errors import NotFoundError
from app.core.sync import SyncChanges, SyncConflictError, SyncContext, SyncOperation, SyncSource
from app.modules.nutrition import service
from app.modules.nutrition.models import PRIVATE, FoodItem
from app.modules.nutrition.schemas import FoodCreate, FoodIn, FoodOut


def _food_json(food: FoodItem) -> dict:
    return FoodOut.model_validate(food).model_dump(mode="json")


def _changes(context: SyncContext, since: datetime | None) -> SyncChanges:
    query = select(FoodItem).where(
        FoodItem.owner_id == context.user.id, FoodItem.visibility == PRIVATE
    )
    if since is not None:
        query = query.where(FoodItem.updated_at > since)
    foods = list(context.db.scalars(query))
    return SyncChanges(
        changed=[_food_json(food) for food in foods if food.deleted_at is None],
        deleted=[food.id for food in foods if food.deleted_at is not None and since is not None],
    )


def _push(context: SyncContext, operation: SyncOperation) -> dict | None:
    db, user = context.db, context.user
    food = db.get(FoodItem, operation.id)
    usable = (
        food is not None
        and food.owner_id == user.id
        and food.visibility == PRIVATE
        and food.deleted_at is None
    )
    if operation.op == "delete":
        if usable:
            service.delete_food(db, food)
        return None
    if food is None:
        data = FoodCreate.model_validate({**(operation.data or {}), "id": operation.id})
        return _food_json(service.create_food(db, user, data))
    if not usable:
        raise NotFoundError("Food not found")
    if operation.base_updated_at is not None and food.updated_at != operation.base_updated_at:
        raise SyncConflictError(_food_json(food))
    return _food_json(service.update_food(db, food, FoodIn.model_validate(operation.data or {})))


SOURCES = [SyncSource("foods", _changes, _push)]
