from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from os import getpid
import logging
from time import perf_counter
from typing import Literal

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, PlainTextResponse
from sqlalchemy import text

from app.api.router import api_router
from app.api.openapi import documented_responses, response_example
from app.core import database
from app.core.config import get_settings
from app.core.exceptions import ErrorResponse, register_exception_handlers
from app.core.logging import configure_logging
from app.core.observability import new_request_id, reset_request_id, runtime_metrics, set_request_id
from app.core.rate_limit import RateLimitMiddleware, build_rate_limit_store
from app.core.security_headers import SecurityHeadersMiddleware
from app.models.base import Base

logger = logging.getLogger(__name__)

_READINESS_SCHEMA = {
    "type": "object",
    "required": ["status", "environment", "checks"],
    "properties": {
        "status": {"type": "string", "enum": ["ready", "not_ready"]},
        "environment": {"type": "string"},
        "checks": {
            "type": "object",
            "additionalProperties": {"type": "string", "enum": ["ok", "error"]},
        },
    },
}
_READINESS_EXAMPLE = {
    "status": "ready",
    "environment": "development",
    "checks": {"database": "ok", "storage": "ok"},
}
_NOT_READY_EXAMPLE = {
    "status": "not_ready",
    "environment": "development",
    "checks": {"database": "error", "storage": "ok"},
}
_READINESS_RESPONSES = documented_responses(
    status.HTTP_200_OK,
    "The API can reach its database and write to repository storage.",
    _READINESS_EXAMPLE,
    status.HTTP_500_INTERNAL_SERVER_ERROR,
    schema=_READINESS_SCHEMA,
)
_READINESS_RESPONSES[status.HTTP_503_SERVICE_UNAVAILABLE] = response_example(
    "The API is running but one or more readiness checks failed.",
    _NOT_READY_EXAMPLE,
    schema=_READINESS_SCHEMA,
)


def check_database_ready() -> bool:
    try:
        with database.engine.connect() as connection:
            connection.execute(text("SELECT 1"))
    except Exception:
        return False
    return True


def check_storage_ready() -> bool:
    settings = get_settings()
    probe_path = settings.storage_path / f".partha-readiness-{getpid()}.tmp"
    try:
        settings.storage_path.mkdir(parents=True, exist_ok=True)
        probe_path.write_text("ok", encoding="utf-8")
        probe_path.unlink(missing_ok=True)
    except OSError:
        return False
    return True


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    settings.storage_path.mkdir(parents=True, exist_ok=True)
    if settings.auto_create_tables:
        Base.metadata.create_all(bind=database.engine)
    try:
        yield
    finally:
        aclose = getattr(app.state.rate_limit_store, "aclose", None)
        if aclose is not None:
            await aclose()


def create_app() -> FastAPI:
    settings = get_settings()
    configure_logging(settings.log_level, settings.log_format)

    app = FastAPI(
        title=settings.app_name,
        version="0.1.0",
        description="Repository architecture intelligence backend for PARTHA.",
        lifespan=lifespan,
    )

    # Registered first (innermost) so it sits inside both SecurityHeadersMiddleware
    # and CORSMiddleware in the wrapped stack: 429 responses still pick up security
    # headers and CORS headers as they bubble back out, instead of a browser client
    # seeing an opaque CORS failure or a response missing the baseline headers.
    app.state.rate_limit_settings = settings
    app.state.rate_limit_store = build_rate_limit_store(settings)
    app.add_middleware(RateLimitMiddleware)
    app.add_middleware(SecurityHeadersMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        # Explicit lists instead of "*": a wildcard is invalid alongside
        # allow_credentials=True and would silently drop credentialed responses.
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type", "X-Request-ID"],
        expose_headers=["X-Request-ID"],
    )
    register_exception_handlers(app)
    app.include_router(api_router)

    @app.middleware("http")
    async def request_observability_middleware(request: Request, call_next):
        request_id = request.headers.get("x-request-id") or new_request_id()
        token = set_request_id(request_id)
        started_at = perf_counter()
        status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
        path = request.url.path
        try:
            response = await call_next(request)
            status_code = response.status_code
            return response
        except Exception:
            logger.exception("Unhandled request error", extra={"method": request.method, "path": path})
            response = JSONResponse(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                headers={"X-Request-ID": request_id},
                content=ErrorResponse(
                    code="internal_server_error",
                    message="An unexpected error occurred.",
                    request_id=request_id,
                ).model_dump(),
            )
            return response
        finally:
            duration_seconds = perf_counter() - started_at
            route = getattr(request.scope.get("route"), "path", path)
            runtime_metrics.record_request(request.method, route, status_code, duration_seconds)
            logger.info(
                "Request completed",
                extra={
                    "method": request.method,
                    "path": path,
                    "route": route,
                    "status_code": status_code,
                    "duration_ms": round(duration_seconds * 1000, 2),
                },
            )
            if "response" in locals():
                response.headers["X-Request-ID"] = request_id
            reset_request_id(token)

    @app.get(
        "/health",
        tags=["system"],
        responses=documented_responses(
            status.HTTP_200_OK,
            "The API process is running.",
            {"status": "ok", "environment": "development"},
            status.HTTP_500_INTERNAL_SERVER_ERROR,
        ),
    )
    def health() -> dict[str, str]:
        return {"status": "ok", "environment": settings.app_env}

    @app.get("/ready", tags=["system"], response_model=None, responses=_READINESS_RESPONSES)
    def readiness() -> dict[str, object] | JSONResponse:
        checks: dict[str, Literal["ok", "error"]] = {}
        checks["database"] = "ok" if check_database_ready() else "error"
        checks["storage"] = "ok" if check_storage_ready() else "error"

        ready = all(check == "ok" for check in checks.values())
        payload = {
            "status": "ready" if ready else "not_ready",
            "environment": settings.app_env,
            "checks": checks,
        }
        if ready:
            return payload
        return JSONResponse(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, content=payload)

    @app.get(
        "/metrics",
        tags=["system"],
        response_class=PlainTextResponse,
        responses=documented_responses(
            status.HTTP_200_OK,
            "Prometheus-compatible runtime metrics.",
            "partha_http_requests_total 1\\n",
            status.HTTP_500_INTERNAL_SERVER_ERROR,
            media_type="text/plain",
            schema={"type": "string"},
        ),
    )
    def metrics() -> str:
        return runtime_metrics.render_prometheus()

    return app


app = create_app()
