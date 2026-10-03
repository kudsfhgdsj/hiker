import uuid
from typing import Annotated

from fastapi import APIRouter, Path, Query, status

from app.core.deps import DbSession
from app.core.errors import error_responses
from app.core.pagination import Page, Paging
from app.modules.auth.deps import AdminUser, CurrentUser
from app.modules.nutrition import service
from app.modules.nutrition.deps import OwnedFood, ReadableFood, Source
from app.modules.nutrition.schemas import (
    BARCODE_PATTERN,
    CatalogFoodPatch,
    FoodCreate,
    FoodIn,
    FoodOut,
)

router = APIRouter(responses=error_responses(401))

SearchText = Annotated[
    str | None, Query(max_length=100, description="Search in name and brand, or an exact barcode")
]


def _page(result, paging) -> Page:
    items, total = result
    return Page(items=items, total=total, limit=paging.limit, offset=paging.offset)


@router.get("/barcode/{ean}", response_model=FoodOut, responses=error_responses(404, 502))
def lookup_barcode(
    ean: Annotated[str, Path(pattern=BARCODE_PATTERN)],
    user: CurrentUser,
    db: DbSession,
    source: Source,
):
    """Find a product by barcode: own foods, then the catalog, then Open Food Facts.

    Results from Open Food Facts are cached in the shared catalog. 404 means the
    product is unknown and the client should offer the form for an own product.
    """
    return service.lookup_barcode(db, user, source, ean)


@router.get("/search", response_model=Page[FoodOut])
def search(user: CurrentUser, db: DbSession, paging: Paging, q: SearchText = None):
    """Own foods and the shared catalog."""
    return _page(service.search(db, user, q=q, limit=paging.limit, offset=paging.offset), paging)


# --- Own foods ---


@router.get("/foods", response_model=Page[FoodOut])
def list_foods(user: CurrentUser, db: DbSession, paging: Paging, q: SearchText = None):
    result = service.list_foods(db, user, q=q, limit=paging.limit, offset=paging.offset)
    return _page(result, paging)


@router.post(
    "/foods",
    response_model=FoodOut,
    status_code=status.HTTP_201_CREATED,
    responses=error_responses(409),
)
def create_food(body: FoodCreate, user: CurrentUser, db: DbSession):
    return service.create_food(db, user, body)


@router.get("/foods/{food_id}", response_model=FoodOut, responses=error_responses(404))
def read_food(food: ReadableFood):
    """An own food, an own proposal or a catalog entry."""
    return food


@router.put("/foods/{food_id}", response_model=FoodOut, responses=error_responses(404))
def update_food(body: FoodIn, food: OwnedFood, db: DbSession):
    return service.update_food(db, food, body)


@router.delete(
    "/foods/{food_id}", status_code=status.HTTP_204_NO_CONTENT, responses=error_responses(404)
)
def delete_food(food: OwnedFood, db: DbSession):
    service.delete_food(db, food)


# --- Catalog ---


@router.post(
    "/foods/{food_id}/propose-to-catalog",
    response_model=FoodOut,
    status_code=status.HTTP_201_CREATED,
    responses=error_responses(404, 409),
)
def propose_to_catalog(food: OwnedFood, user: CurrentUser, db: DbSession):
    return service.propose(db, user, food)


@router.get("/catalog/mine", response_model=Page[FoodOut])
def list_own_proposals(user: CurrentUser, db: DbSession, paging: Paging):
    """The user's own proposals with their status."""
    result = service.list_own_proposals(db, user, limit=paging.limit, offset=paging.offset)
    return _page(result, paging)


@router.get("/catalog/pending", response_model=Page[FoodOut], responses=error_responses(403))
def list_pending(_admin: AdminUser, db: DbSession, paging: Paging):
    return _page(service.list_pending(db, limit=paging.limit, offset=paging.offset), paging)


@router.patch(
    "/catalog/{catalog_id}", response_model=FoodOut, responses=error_responses(403, 404, 409)
)
def moderate(catalog_id: uuid.UUID, body: CatalogFoodPatch, _admin: AdminUser, db: DbSession):
    """Approve or reject a proposal and optionally correct its data (admin)."""
    return service.moderate(db, service.get_proposal(db, catalog_id), body)
