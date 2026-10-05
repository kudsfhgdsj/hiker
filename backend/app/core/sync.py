"""Offline sync: modules register what they can deliver and accept.

Core only keeps the registry. The endpoints live in the `sync` module; every
other module registers its collections in `register(app)` and stays unaware of
the sync module.
"""

import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Literal

from fastapi import FastAPI
from pydantic import AwareDatetime, BaseModel, Field
from sqlalchemy.orm import Session

from app.core.storage import Storage


class SyncOperation(BaseModel):
    """One local change of a client, made while it was offline."""

    collection: str = Field(max_length=40)
    op: Literal["upsert", "delete"]
    id: uuid.UUID
    base_version: int | None = Field(
        default=None, description="Version the change is based on (tours)"
    )
    base_updated_at: AwareDatetime | None = Field(
        default=None, description="updated_at the change is based on (records without version)"
    )
    data: dict | None = Field(default=None, description="The record, for upsert")


@dataclass(frozen=True)
class SyncContext:
    db: Session
    user: Any
    storage: Storage


@dataclass(frozen=True)
class SyncChanges:
    """What changed in a collection since a point in time."""

    changed: list[dict] = field(default_factory=list)
    deleted: list[uuid.UUID] = field(default_factory=list)
    # True: `changed` is the whole collection; the client replaces its copy.
    full: bool = False
    # All ids the user may still see, for collections where access can be taken away.
    ids: list[uuid.UUID] | None = None


class SyncConflictError(Exception):
    """The record was changed on the server since the client's base state."""

    def __init__(self, current: dict):
        super().__init__("conflict")
        self.current = current


@dataclass(frozen=True)
class SyncSource:
    collection: str
    changes: Callable[[SyncContext, datetime | None], SyncChanges]
    # Applies an operation and returns the stored record (None after a delete).
    # Collections without it are read-only for the sync.
    push: Callable[[SyncContext, SyncOperation], dict | None] | None = None


def register_sync_source(app: FastAPI, source: SyncSource) -> None:
    sources: dict[str, SyncSource] = getattr(app.state, "sync_sources", {})
    sources[source.collection] = source
    app.state.sync_sources = sources


def sync_sources(app: FastAPI) -> dict[str, SyncSource]:
    return getattr(app.state, "sync_sources", {})
