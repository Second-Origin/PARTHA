import logging

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.observability import get_request_id

logger = logging.getLogger(__name__)


def request_id_headers() -> dict[str, str]:
    request_id = get_request_id()
    return {"X-Request-ID": request_id} if request_id else {}


class ErrorResponse(BaseModel):
    code: str
    message: str
    details: dict[str, object] | None = None
    request_id: str | None = None


class ServiceError(Exception):
    status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
    code = "service_error"

    def __init__(self, message: str, details: dict[str, object] | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.details = details


class NotFoundError(ServiceError):
    status_code = status.HTTP_404_NOT_FOUND
    code = "not_found"


class ValidationServiceError(ServiceError):
    status_code = status.HTTP_422_UNPROCESSABLE_CONTENT
    code = "validation_error"


class ConflictServiceError(ServiceError):
    status_code = status.HTTP_409_CONFLICT
    code = "conflict_error"


class TimeoutServiceError(ServiceError):
    status_code = status.HTTP_504_GATEWAY_TIMEOUT
    code = "timeout_error"


class ExternalServiceError(ServiceError):
    status_code = status.HTTP_502_BAD_GATEWAY
    code = "external_service_error"


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(ServiceError)
    async def service_error_handler(_: Request, exc: ServiceError) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            headers=request_id_headers(),
            content=ErrorResponse(
                code=exc.code,
                message=exc.message,
                details=exc.details,
                request_id=get_request_id(),
            ).model_dump(),
        )

    @app.exception_handler(RequestValidationError)
    async def validation_error_handler(_: Request, exc: RequestValidationError) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            headers=request_id_headers(),
            content=ErrorResponse(
                code="request_validation_error",
                message="Request validation failed.",
                details={"errors": exc.errors()},
                request_id=get_request_id(),
            ).model_dump(),
        )

    @app.exception_handler(StarletteHTTPException)
    async def http_error_handler(_: Request, exc: StarletteHTTPException) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            headers=request_id_headers(),
            content=ErrorResponse(code="http_error", message=str(exc.detail), request_id=get_request_id()).model_dump(),
        )

    @app.exception_handler(Exception)
    async def unhandled_error_handler(request: Request, exc: Exception) -> JSONResponse:
        logger.exception(
            "Unhandled request error",
            extra={"path": request.url.path, "method": request.method},
            exc_info=True,
        )
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            headers=request_id_headers(),
            content=ErrorResponse(
                code="internal_server_error",
                message="An unexpected error occurred.",
                request_id=get_request_id(),
            ).model_dump(),
        )
