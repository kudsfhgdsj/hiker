from fastapi import FastAPI
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from app import __version__
from app.core.config import API_PREFIX, Settings, get_settings
from app.core.deps import DbSession
from app.core.errors import install_error_handlers
from app.core.registry import load_modules


class ModuleOut(BaseModel):
    name: str
    version: str


class HealthOut(BaseModel):
    status: str


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    app = FastAPI(
        title="hiker API",
        version=__version__,
        openapi_url=f"{API_PREFIX}/openapi.json",
        docs_url=f"{API_PREFIX}/docs",
        redoc_url=None,
    )
    install_error_handlers(app)
    app.state.modules = load_modules(app, settings.module_names)

    @app.get("/healthz", response_model=HealthOut, tags=["system"])
    def healthz(db: DbSession):
        try:
            db.execute(text("SELECT 1"))
        except SQLAlchemyError:
            return JSONResponse({"status": "unavailable"}, status_code=503)
        return HealthOut(status="ok")

    @app.get(f"{API_PREFIX}/modules", response_model=list[ModuleOut], tags=["system"])
    def list_modules():
        """Enabled modules, so that clients can show only the available features."""
        return [ModuleOut(name=info.name, version=info.version) for info in app.state.modules]

    return app
