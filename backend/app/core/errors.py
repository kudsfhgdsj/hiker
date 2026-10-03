from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel


class AppError(Exception):
    """Base class for errors that are returned to the client in a uniform format."""

    status_code = 400
    code = "bad_request"

    def __init__(self, message: str, *, code: str | None = None):
        super().__init__(message)
        self.message = message
        if code is not None:
            self.code = code

    @property
    def headers(self) -> dict[str, str] | None:
        return None


class UnauthorizedError(AppError):
    status_code = 401
    code = "unauthorized"

    @property
    def headers(self) -> dict[str, str]:
        return {"WWW-Authenticate": "Bearer"}


class ForbiddenError(AppError):
    status_code = 403
    code = "forbidden"


class NotFoundError(AppError):
    status_code = 404
    code = "not_found"


class ConflictError(AppError):
    status_code = 409
    code = "conflict"


class ErrorBody(BaseModel):
    code: str
    message: str


class ErrorResponse(BaseModel):
    error: ErrorBody


def error_responses(*status_codes: int) -> dict[int | str, dict]:
    """OpenAPI `responses` entries for the uniform error format."""
    return {status: {"model": ErrorResponse} for status in status_codes}


def install_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    def _handle_app_error(_request: Request, exc: AppError) -> JSONResponse:
        body = ErrorResponse(error=ErrorBody(code=exc.code, message=exc.message))
        return JSONResponse(body.model_dump(), status_code=exc.status_code, headers=exc.headers)
