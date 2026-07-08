from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from starlette.exceptions import HTTPException as StarletteHTTPException


class ErrorResponse(BaseModel):
    code: str
    message: str
    details: dict[str, object] | None = None


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
            content=ErrorResponse(code=exc.code, message=exc.message, details=exc.details).model_dump(),
        )

    @app.exception_handler(RequestValidationError)
    async def validation_error_handler(_: Request, exc: RequestValidationError) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            content=ErrorResponse(
                code="request_validation_error",
                message="Request validation failed.",
                details={"errors": exc.errors()},
            ).model_dump(),
        )

    @app.exception_handler(StarletteHTTPException)
    async def http_error_handler(_: Request, exc: StarletteHTTPException) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content=ErrorResponse(code="http_error", message=str(exc.detail)).model_dump(),
        )
