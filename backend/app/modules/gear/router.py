import uuid
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Query, Response, UploadFile, status

from app.core import files
from app.core.config import get_settings
from app.core.deps import DbSession, FileStorage
from app.core.errors import NotFoundError, PayloadTooLargeError, error_responses
from app.core.pagination import Page, Paging
from app.modules.auth.deps import AdminUser, CurrentUser
from app.modules.gear import catalog, service
from app.modules.gear.attributes import KINDS
from app.modules.gear.deps import (
    EditableType,
    OwnedItem,
    OwnedList,
    OwnedTag,
    ReadableCatalogItem,
)
from app.modules.gear.models import CURRENCY, GearCatalogItem, GearType
from app.modules.gear.schemas import (
    AttributeOut,
    CatalogItemOut,
    CatalogItemPatch,
    GearItemCreate,
    GearItemIn,
    GearItemOut,
    GearListCreate,
    GearListIn,
    GearListOut,
    GearMeta,
    GearSummaryOut,
    GearTagCreate,
    GearTagIn,
    GearTagOut,
    GearTypeCreate,
    GearTypeIn,
    GearTypeOut,
    KindOut,
)
from app.modules.gear.summary import summarize

router = APIRouter(responses=error_responses(401))

IMAGE_RESPONSE = {200: {"content": {"image/jpeg": {}}}}


def _image_response(db, storage, file_id) -> Response:
    file, data = files.load_file(db, storage, file_id)
    headers = {"Cache-Control": "private, max-age=86400", "ETag": f'"{file.sha256}"'}
    return Response(content=data, media_type=file.mime, headers=headers)


def _read_upload(upload: UploadFile) -> bytes:
    limit = get_settings().max_upload_mb * 1024 * 1024
    data = upload.file.read(limit + 1)
    if len(data) > limit:
        raise PayloadTooLargeError(f"File is larger than {get_settings().max_upload_mb} MB")
    return data


def _type_out(gear_type: GearType) -> GearTypeOut:
    return GearTypeOut(
        id=gear_type.id,
        name=gear_type.name,
        sort_order=gear_type.sort_order,
        standard=gear_type.owner_id is None,
        kind=gear_type.kind,
    )


# --- Types ---


@router.get("/types", response_model=list[GearTypeOut])
def list_types(user: CurrentUser, db: DbSession):
    """Standard list plus the user's own types."""
    return [_type_out(gear_type) for gear_type in service.list_types(db, user)]


@router.post(
    "/types",
    response_model=GearTypeOut,
    status_code=status.HTTP_201_CREATED,
    responses=error_responses(403, 409),
)
def create_type(body: GearTypeCreate, user: CurrentUser, db: DbSession):
    return _type_out(service.create_type(db, user, body))


@router.put(
    "/types/{type_id}", response_model=GearTypeOut, responses=error_responses(403, 404, 409)
)
def update_type(body: GearTypeIn, gear_type: EditableType, user: CurrentUser, db: DbSession):
    return _type_out(service.update_type(db, user, gear_type, body))


@router.delete(
    "/types/{type_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    responses=error_responses(403, 404),
)
def delete_type(gear_type: EditableType, db: DbSession):
    service.delete_type(db, gear_type)


# --- Tags ---


@router.get("/tags", response_model=list[GearTagOut])
def list_tags(user: CurrentUser, db: DbSession):
    return service.list_tags(db, user)


@router.post(
    "/tags",
    response_model=GearTagOut,
    status_code=status.HTTP_201_CREATED,
    responses=error_responses(409),
)
def create_tag(body: GearTagCreate, user: CurrentUser, db: DbSession):
    return service.create_tag(db, user, body)


@router.put("/tags/{tag_id}", response_model=GearTagOut, responses=error_responses(404, 409))
def update_tag(body: GearTagIn, tag: OwnedTag, user: CurrentUser, db: DbSession):
    return service.update_tag(db, user, tag, body)


@router.delete(
    "/tags/{tag_id}", status_code=status.HTTP_204_NO_CONTENT, responses=error_responses(404)
)
def delete_tag(tag: OwnedTag, db: DbSession):
    service.delete_tag(db, tag)


# --- Meta ---


@router.get("/meta", response_model=GearMeta)
def read_meta(_user: CurrentUser):
    """Currency, upload limits and the extra attributes per kind of gear type."""
    return GearMeta(
        currency=CURRENCY,
        image_formats=["JPEG", "PNG", "WebP"],
        max_upload_mb=get_settings().max_upload_mb,
        kinds=[
            KindOut(
                kind=kind,
                attributes=[
                    AttributeOut(
                        key=d.key,
                        type=d.type,
                        unit=d.unit,
                        minimum=d.minimum,
                        maximum=d.maximum,
                        options=list(d.options),
                    )
                    for d in definitions
                ],
            )
            for kind, definitions in KINDS.items()
        ],
    )


# --- Items ---


def _item_filter(
    q: Annotated[str | None, Query(max_length=100, description="Search in name and brand")] = None,
    type_id: uuid.UUID | None = None,
    status: Literal["active", "retired"] | None = None,
    tag_id: Annotated[
        list[uuid.UUID] | None,
        Query(max_length=20, description="Repeatable; items must carry all given tags"),
    ] = None,
    favorite: Annotated[
        bool | None, Query(description="true: only favourites, false: only the others")
    ] = None,
) -> service.ItemFilter:
    return service.ItemFilter(
        q=q, type_id=type_id, status=status, tag_ids=tuple(tag_id or ()), favorite=favorite
    )


ItemFilters = Annotated[service.ItemFilter, Depends(_item_filter)]


@router.get("/items", response_model=Page[GearItemOut])
def list_items(user: CurrentUser, db: DbSession, paging: Paging, filters: ItemFilters):
    items, total = service.list_items(db, user, filters, limit=paging.limit, offset=paging.offset)
    return Page(items=items, total=total, limit=paging.limit, offset=paging.offset)


@router.get("/summary", response_model=GearSummaryOut)
def summarize_items(
    user: CurrentUser,
    db: DbSession,
    filters: ItemFilters,
    group_by: Literal["type", "tag", "status", "brand"] | None = None,
):
    """Count, weight and purchase value of the gear, optionally per group.

    Takes the same filters as the item list. With `group_by=tag` an item counts
    in every one of its tags, so the groups can add up to more than the total.
    """
    return summarize(db, user, filters, group_by)


@router.post(
    "/items",
    response_model=GearItemOut,
    status_code=status.HTTP_201_CREATED,
    responses=error_responses(409),
)
def create_item(body: GearItemCreate, user: CurrentUser, db: DbSession, storage: FileStorage):
    return service.create_item(db, storage, user, body)


@router.get("/items/{item_id}", response_model=GearItemOut, responses=error_responses(404))
def read_item(item: OwnedItem):
    return item


@router.put("/items/{item_id}", response_model=GearItemOut, responses=error_responses(404))
def update_item(body: GearItemIn, item: OwnedItem, user: CurrentUser, db: DbSession):
    return service.update_item(db, user, item, body)


@router.delete(
    "/items/{item_id}", status_code=status.HTTP_204_NO_CONTENT, responses=error_responses(404)
)
def delete_item(item: OwnedItem, db: DbSession, storage: FileStorage):
    service.delete_item(db, storage, item)


@router.put("/items/{item_id}/favorite", response_model=GearItemOut, responses=error_responses(404))
def mark_favorite(item: OwnedItem, user: CurrentUser, db: DbSession):
    """Mark the item as a favourite (it gets the tag "favorite")."""
    return service.set_favorite(db, user, item, True)


@router.delete(
    "/items/{item_id}/favorite", response_model=GearItemOut, responses=error_responses(404)
)
def unmark_favorite(item: OwnedItem, user: CurrentUser, db: DbSession):
    return service.set_favorite(db, user, item, False)


@router.post(
    "/items/{item_id}/image", response_model=GearItemOut, responses=error_responses(404, 413)
)
def upload_item_image(file: UploadFile, item: OwnedItem, db: DbSession, storage: FileStorage):
    """Set the image (JPEG, PNG or WebP). It is re-encoded as JPEG without metadata."""
    return service.set_item_image(db, storage, item, _read_upload(file))


@router.get(
    "/items/{item_id}/image",
    response_class=Response,
    responses={**IMAGE_RESPONSE, **error_responses(404)},
)
def read_item_image(item: OwnedItem, db: DbSession, storage: FileStorage):
    return _image_response(db, storage, item.image_file_id)


@router.delete(
    "/items/{item_id}/image",
    status_code=status.HTTP_204_NO_CONTENT,
    responses=error_responses(404),
)
def delete_item_image(item: OwnedItem, db: DbSession, storage: FileStorage):
    service.remove_item_image(db, storage, item)


# --- Catalog ---


@router.post(
    "/items/{item_id}/propose-to-catalog",
    response_model=CatalogItemOut,
    status_code=status.HTTP_201_CREATED,
    responses=error_responses(404, 409),
)
def propose_to_catalog(item: OwnedItem, user: CurrentUser, db: DbSession, storage: FileStorage):
    """Propose the product data of an item (no personal fields) for the shared catalog."""
    return catalog.propose(db, storage, user, item)


@router.get("/catalog", response_model=Page[CatalogItemOut])
def search_catalog(
    _user: CurrentUser,
    db: DbSession,
    paging: Paging,
    q: Annotated[str | None, Query(max_length=100, description="Search in name and brand")] = None,
):
    """Approved catalog entries."""
    items, total = catalog.search(db, q=q, limit=paging.limit, offset=paging.offset)
    return Page(items=items, total=total, limit=paging.limit, offset=paging.offset)


@router.get("/catalog/mine", response_model=Page[CatalogItemOut])
def list_own_proposals(user: CurrentUser, db: DbSession, paging: Paging):
    """The user's own proposals with their status (pending, approved, rejected)."""
    items, total = catalog.list_own_proposals(db, user, limit=paging.limit, offset=paging.offset)
    return Page(items=items, total=total, limit=paging.limit, offset=paging.offset)


@router.get("/catalog/pending", response_model=Page[CatalogItemOut], responses=error_responses(403))
def list_pending_catalog_items(_admin: AdminUser, db: DbSession, paging: Paging):
    items, total = catalog.list_pending(db, limit=paging.limit, offset=paging.offset)
    return Page(items=items, total=total, limit=paging.limit, offset=paging.offset)


@router.patch(
    "/catalog/{catalog_id}", response_model=CatalogItemOut, responses=error_responses(403, 404)
)
def moderate_catalog_item(
    catalog_id: uuid.UUID, body: CatalogItemPatch, _admin: AdminUser, db: DbSession
):
    """Approve or reject a proposal and optionally correct its product data (admin)."""
    entry = db.get(GearCatalogItem, catalog_id)
    if entry is None:
        raise NotFoundError("Catalog entry not found")
    return catalog.moderate(db, entry, body)


@router.get(
    "/catalog/{catalog_id}/image",
    response_class=Response,
    responses={**IMAGE_RESPONSE, **error_responses(404)},
)
def read_catalog_image(entry: ReadableCatalogItem, db: DbSession, storage: FileStorage):
    return _image_response(db, storage, entry.image_file_id)


# --- Packing lists ---


@router.get("/lists", response_model=list[GearListOut])
def list_lists(user: CurrentUser, db: DbSession):
    return [service.list_out(db, gear_list) for gear_list in service.list_lists(db, user)]


@router.post(
    "/lists",
    response_model=GearListOut,
    status_code=status.HTTP_201_CREATED,
    responses=error_responses(409),
)
def create_list(body: GearListCreate, user: CurrentUser, db: DbSession):
    return service.list_out(db, service.create_list(db, user, body))


@router.get("/lists/{list_id}", response_model=GearListOut, responses=error_responses(404))
def read_list(gear_list: OwnedList, db: DbSession):
    return service.list_out(db, gear_list)


@router.put("/lists/{list_id}", response_model=GearListOut, responses=error_responses(404))
def update_list(body: GearListIn, gear_list: OwnedList, user: CurrentUser, db: DbSession):
    return service.list_out(db, service.update_list(db, user, gear_list, body))


@router.delete(
    "/lists/{list_id}", status_code=status.HTTP_204_NO_CONTENT, responses=error_responses(404)
)
def delete_list(gear_list: OwnedList, db: DbSession):
    service.delete_list(db, gear_list)
