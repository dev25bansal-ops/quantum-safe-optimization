"""API Routers for QSOP."""

from fastapi import APIRouter

from .health import router as health_router
from .jobs import router as jobs_router
from .algorithms import router as algorithms_router
from .keys import router as keys_router
from .auth import router as auth_router


def create_api_router() -> APIRouter:
    """Create the main API router with all sub-routers mounted."""
    api_router = APIRouter()
    
    api_router.include_router(health_router, tags=["health"])
    api_router.include_router(jobs_router, prefix="/jobs", tags=["jobs"])
    api_router.include_router(algorithms_router, tags=["algorithms"])
    api_router.include_router(keys_router, prefix="/keys", tags=["keys"])
    
    return api_router


__all__ = [
    "create_api_router",
    "health_router",
    "jobs_router",
    "algorithms_router",
    "keys_router",
    "auth_router",
]
