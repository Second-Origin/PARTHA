from fastapi import APIRouter

from app.api.routes import ai, analysis, auth, documentation, intelligence, reports, repositories, waitlist

api_router = APIRouter()
api_router.include_router(auth.router)
api_router.include_router(repositories.router)
api_router.include_router(intelligence.router)
api_router.include_router(analysis.router)
api_router.include_router(ai.router)
api_router.include_router(documentation.router)
api_router.include_router(reports.router)
api_router.include_router(waitlist.router)
