"""Module reports: what all tours of a user add up to.

Totals, climbed peaks, the days out as a calendar, all tracks for one map, and
the peaks the user still wishes for. Reads the tours of `protocols`; `protocols`
knows nothing of it.
"""

from fastapi import FastAPI

from app.core.config import API_PREFIX
from app.core.registry import ModuleInfo

MODULE_INFO = ModuleInfo(name="reports", version="0.1.0", depends_on=("auth", "protocols"))


def register(app: FastAPI) -> None:
    from app.modules.reports.router import router

    app.include_router(router, prefix=f"{API_PREFIX}/reports", tags=["reports"])
