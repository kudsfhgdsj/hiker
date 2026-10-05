"""Module protocols: tours with gear, food, peaks and waypoints, shared with other users.

Uses `gear` and `nutrition` only through their service functions and ids.
"""

from fastapi import FastAPI

from app.core.config import API_PREFIX
from app.core.log_redaction import redact_paths_in_access_log
from app.core.registry import ModuleInfo
from app.core.sync import register_sync_source

MODULE_INFO = ModuleInfo(
    name="protocols", version="0.1.0", depends_on=("auth", "gear", "nutrition")
)


def register(app: FastAPI) -> None:
    from app.modules.protocols.public import PUBLIC_API_PATH, PUBLIC_PAGE_PATH
    from app.modules.protocols.router import public_router, router
    from app.modules.protocols.sync import SOURCES

    app.include_router(router, prefix=API_PREFIX, tags=["tours"])
    app.include_router(public_router, prefix=API_PREFIX, tags=["public"])
    # Tokens of public links are secrets and must not show up in the access log.
    redact_paths_in_access_log(PUBLIC_API_PATH, PUBLIC_PAGE_PATH)
    for source in SOURCES:
        register_sync_source(app, source)
