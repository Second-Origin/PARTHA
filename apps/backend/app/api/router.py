from fastapi import APIRouter

from app.api.routes import ai, analysis, documentation, reports, repositories

api_router = APIRouter()
api_router.include_router(repositories.router)
api_router.include_router(analysis.router)
api_router.include_router(ai.router)
api_router.include_router(documentation.router)
api_router.include_router(reports.router)
