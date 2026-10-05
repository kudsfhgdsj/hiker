"""Module nutrition: personal foods, barcode lookup and the shared food catalog."""

from fastapi import FastAPI

from app.core.config import API_PREFIX
from app.core.registry import ModuleInfo
from app.core.sync import register_sync_source

MODULE_INFO = ModuleInfo(name="nutrition", version="0.1.0", depends_on=("auth",))


def register(app: FastAPI) -> None:
    from app.modules.nutrition.router import router
    from app.modules.nutrition.sync import SOURCES

    app.include_router(router, prefix=f"{API_PREFIX}/nutrition", tags=["nutrition"])
    for source in SOURCES:
        register_sync_source(app, source)
