"""Module auth: users, profile, login and tokens.

Public interface for other modules: `deps.CurrentUser`, `deps.AdminUser`,
`deps.is_admin`, the functions in `service` and `models.User` (read only).
"""

from fastapi import FastAPI

from app.core.config import API_PREFIX
from app.core.registry import ModuleInfo

MODULE_INFO = ModuleInfo(name="auth", version="0.1.0")


def register(app: FastAPI) -> None:
    from app.modules.auth.router import router

    app.include_router(router, prefix=API_PREFIX)
