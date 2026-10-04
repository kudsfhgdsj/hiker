"""Module maps: map tiles from the own server, cached from the tile source."""

from fastapi import FastAPI

from app.core.config import API_PREFIX
from app.core.registry import ModuleInfo

MODULE_INFO = ModuleInfo(name="maps", version="0.2.0", depends_on=("auth",))


def register(app: FastAPI) -> None:
    from app.modules.maps.router import router

    app.include_router(router, prefix=f"{API_PREFIX}/maps", tags=["maps"])
