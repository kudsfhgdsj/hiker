"""Module sync: the endpoints of the offline sync.

The collections come from the other modules, which register them with core.
"""

from fastapi import FastAPI

from app.core.config import API_PREFIX
from app.core.registry import ModuleInfo

MODULE_INFO = ModuleInfo(name="sync", version="0.1.0", depends_on=("auth",))


def register(app: FastAPI) -> None:
    from app.modules.sync.router import router

    app.include_router(router, prefix=f"{API_PREFIX}/sync", tags=["sync"])
