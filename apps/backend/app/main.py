from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from os import getpid
from typing import Literal

from fastapi import FastAPI, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text

from app.api.router import api_router
from app.core import database
from app.core.config import get_settings
from app.core.exceptions import register_exception_handlers
from app.core.logging import configure_logging
from app.models import RepositoryRecord  # noqa: F401 - imported so metadata includes model
from app.models.base import Base


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

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    register_exception_handlers(app)
    app.include_router(api_router)

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

    return app


app = create_app()
