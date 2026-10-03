from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy.orm.exc import StaleDataError


class AppError(Exception):
    """Base class for errors that are returned to the client in a uniform format."""

    status_code = 400
    code = "bad_request"
    # Additional top-level fields of the response body, next to "error".
    extra: dict | None = None

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


class PayloadTooLargeError(AppError):
    status_code = 413
    code = "payload_too_large"


class UnprocessableError(AppError):
    status_code = 422
    code = "unprocessable"


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
        content = body.model_dump() | (exc.extra or {})
        return JSONResponse(content, status_code=exc.status_code, headers=exc.headers)

    @app.exception_handler(StaleDataError)
    def _handle_stale_data(_request: Request, _exc: StaleDataError) -> JSONResponse:
        # Optimistic locking: a concurrent request changed the record first.
        error = ErrorBody(code="version_conflict", message="The record was changed in the meantime")
        return JSONResponse(ErrorResponse(error=error).model_dump(), status_code=409)
