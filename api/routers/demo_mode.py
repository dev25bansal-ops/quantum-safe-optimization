"""
Demo Mode Router.
Provides endpoints to check demo mode status.
"""

from fastapi import APIRouter
from api.security.demo_mode import get_demo_mode_status

router = APIRouter()


@router.get("/demo-mode/status")
async def get_demo_status():
    """Get demo mode configuration status."""
    return get_demo_mode_status()
