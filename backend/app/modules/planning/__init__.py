"""Module planning: routes planned ahead of a tour, along paths or as straight lines.

Uses `protocols` only for the evaluation of tracks and the elevation lookup.
"""

from fastapi import FastAPI

from app.core.config import API_PREFIX
from app.core.registry import ModuleInfo
from app.core.sync import register_sync_source

MODULE_INFO = ModuleInfo(name="planning", version="0.1.0", depends_on=("auth", "protocols"))


def register(app: FastAPI) -> None:
    from app.modules.planning.router import router
    from app.modules.planning.sync import SOURCES

    app.include_router(router, prefix=f"{API_PREFIX}/planning", tags=["planning"])
    for source in SOURCES:
        register_sync_source(app, source)
