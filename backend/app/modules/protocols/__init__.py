"""Module protocols: tours with gear, food, peaks and waypoints, shared with other users.

Uses `gear` and `nutrition` only through their service functions and ids.
"""

from fastapi import FastAPI

from app.core.config import API_PREFIX
from app.core.registry import ModuleInfo

MODULE_INFO = ModuleInfo(
    name="protocols", version="0.1.0", depends_on=("auth", "gear", "nutrition")
)


def register(app: FastAPI) -> None:
    from app.modules.protocols.router import router

    app.include_router(router, prefix=API_PREFIX, tags=["tours"])
