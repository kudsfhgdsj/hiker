import logging
import uuid
from datetime import datetime
from typing import Annotated, Literal

from fastapi import APIRouter, Query, Request
from pydantic import AwareDatetime, BaseModel, Field, ValidationError
from sqlalchemy.exc import SQLAlchemyError

from app.core.db import utcnow
from app.core.deps import DbSession, FileStorage
from app.core.errors import AppError, error_responses
from app.core.sync import SyncConflictError, SyncContext, SyncOperation, sync_sources
from app.modules.auth.deps import CurrentUser

logger = logging.getLogger(__name__)
router = APIRouter(responses=error_responses(401))


class CollectionChanges(BaseModel):
    changed: list[dict]
    deleted: list[uuid.UUID]
    full: bool = Field(description="changed is the whole collection: replace the local copy")
    ids: list[uuid.UUID] | None = Field(
        description="All ids still visible; drop local records that are not listed"
    )


class ChangesOut(BaseModel):
    server_time: datetime = Field(description="Pass it as `since` in the next request")
    collections: dict[str, CollectionChanges]


class PushIn(BaseModel):
    operations: list[SyncOperation] = Field(max_length=500)


class PushResult(BaseModel):
    collection: str
    id: uuid.UUID
    status: Literal["ok", "conflict", "error"]
    record: dict | None = Field(default=None, description="The stored record after `ok`")
    current: dict | None = Field(default=None, description="The server's record after `conflict`")
    code: str | None = None
    message: str | None = None


class PushOut(BaseModel):
    results: list[PushResult]


@router.get("/changes", response_model=ChangesOut)
def read_changes(
    request: Request,
    user: CurrentUser,
    db: DbSession,
    storage: FileStorage,
    since: Annotated[
        AwareDatetime | None,
        Query(description="server_time of the last sync; omit for everything"),
    ] = None,
):
    """Everything that changed for the user since the last sync, per collection."""
    # Taken before reading, so that nothing written meanwhile is missed next time.
    server_time = utcnow()
    context = SyncContext(db=db, user=user, storage=storage)
    collections = {}
    for name, source in sync_sources(request.app).items():
        changes = source.changes(context, since)
        collections[name] = CollectionChanges(
            changed=changes.changed, deleted=changes.deleted, full=changes.full, ids=changes.ids
        )
    return ChangesOut(server_time=server_time, collections=collections)


@router.post("/push", response_model=PushOut)
def push_changes(
    body: PushIn, request: Request, user: CurrentUser, db: DbSession, storage: FileStorage
):
    """Apply changes made offline, in order. Every operation gets its own result:

    `ok` with the stored record, `conflict` with the server's record if it was
    changed since the base state, or `error`. One failing operation does not
    stop the others.
    """
    context = SyncContext(db=db, user=user, storage=storage)
    sources = sync_sources(request.app)
    results = []
    for operation in body.operations:
        result = PushResult(collection=operation.collection, id=operation.id, status="ok")
        source = sources.get(operation.collection)
        try:
            if source is None or source.push is None:
                raise AppError("Unknown collection", code="unknown_collection")
            result.record = source.push(context, operation)
        except SyncConflictError as conflict:
            db.rollback()
            result.status, result.current = "conflict", conflict.current
        except AppError as error:
            db.rollback()
            result.status, result.code, result.message = "error", error.code, error.message
        except ValidationError as error:
            db.rollback()
            result.status, result.code = "error", "validation"
            result.message = "; ".join(e["msg"] for e in error.errors())
        except SQLAlchemyError:
            db.rollback()
            logger.exception("Sync operation failed")
            result.status, result.code = "error", "internal"
        results.append(result)
    return PushOut(results=results)
