"""Module gear: personal gear, gear types, packing lists and the shared catalog."""

from fastapi import FastAPI

from app.core.config import API_PREFIX
from app.core.registry import ModuleInfo
from app.core.sync import register_sync_source

MODULE_INFO = ModuleInfo(name="gear", version="0.1.0", depends_on=("auth",))


def register(app: FastAPI) -> None:
    from app.modules.gear.router import router
    from app.modules.gear.sync import SOURCES

    app.include_router(router, prefix=f"{API_PREFIX}/gear", tags=["gear"])
    for source in SOURCES:
        register_sync_source(app, source)
