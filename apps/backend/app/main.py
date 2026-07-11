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
from app.core import database
from app.core.config import get_settings
from app.core.exceptions import ErrorResponse, register_exception_handlers
from app.core.logging import configure_logging
from app.core.observability import new_request_id, reset_request_id, runtime_metrics, set_request_id
from app.core.security_headers import SecurityHeadersMiddleware
from app.models import RepositoryRecord, User  # noqa: F401 - imported so metadata includes models
from app.models.base import Base

logger = logging.getLogger(__name__)


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
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    settings.storage_path.mkdir(parents=True, exist_ok=True)
    if settings.auto_create_tables:
        Base.metadata.create_all(bind=database.engine)
    yield


def create_app() -> FastAPI:
    settings = get_settings()
    configure_logging(settings.log_level, settings.log_format)

    app = FastAPI(
        title=settings.app_name,
        version="0.1.0",
        description="Repository architecture intelligence backend for PARTHA.",
        lifespan=lifespan,
    )

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

    @app.get("/health", tags=["system"])
    def health() -> dict[str, str]:
        return {"status": "ok", "environment": settings.app_env}

    @app.get("/ready", tags=["system"], response_model=None)
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

    @app.get("/metrics", tags=["system"], response_class=PlainTextResponse)
    def metrics() -> str:
        return runtime_metrics.render_prometheus()

    return app


app = create_app()
