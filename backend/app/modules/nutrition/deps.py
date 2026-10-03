"""Central access checks and the food source of the nutrition module."""

import uuid
from functools import lru_cache
from typing import Annotated

from fastapi import Depends

from app import __version__
from app.core.config import get_settings
from app.core.deps import DbSession
from app.core.errors import NotFoundError
from app.modules.auth.deps import CurrentUser
from app.modules.nutrition.models import CATALOG, PRIVATE, FoodItem
from app.modules.nutrition.sources import DisabledFoodSource, FoodSource, OpenFoodFactsSource


@lru_cache
def get_food_source() -> FoodSource:
    settings = get_settings()
    if not settings.openfoodfacts_base_url:
        return DisabledFoodSource()
    # Open Food Facts asks every client to identify itself.
    user_agent = f"hiker/{__version__} ({settings.public_base_url})"
    return OpenFoodFactsSource(settings.openfoodfacts_base_url, user_agent)


def _is_own(food: FoodItem | None, user) -> bool:
    return (
        food is not None
        and food.owner_id == user.id
        and food.visibility == PRIVATE
        and food.deleted_at is None
    )


def get_owned_food(food_id: uuid.UUID, user: CurrentUser, db: DbSession) -> FoodItem:
    food = db.get(FoodItem, food_id)
    # Foreign foods answer like missing ones, so that ids cannot be probed.
    if not _is_own(food, user):
        raise NotFoundError("Food not found")
    return food


def get_readable_food(food_id: uuid.UUID, user: CurrentUser, db: DbSession) -> FoodItem:
    """Own foods, own proposals and everything in the shared catalog."""
    food = db.get(FoodItem, food_id)
    if food is None or food.deleted_at is not None:
        raise NotFoundError("Food not found")
    if food.visibility != CATALOG and user.id not in (food.owner_id, food.proposed_by):
        raise NotFoundError("Food not found")
    return food


OwnedFood = Annotated[FoodItem, Depends(get_owned_food)]
ReadableFood = Annotated[FoodItem, Depends(get_readable_food)]
Source = Annotated[FoodSource, Depends(get_food_source)]
