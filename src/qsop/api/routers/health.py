"""Health check endpoints for Kubernetes probes."""

from __future__ import annotations

import time
from typing import Any

from fastapi import APIRouter, Depends, Response
from pydantic import BaseModel

from qsop.api.deps import get_db, get_settings, Settings

router = APIRouter()

_start_time = time.time()


class HealthStatus(BaseModel):
    """Health check response model."""

    status: str
    version: str = "1.0.0"
    uptime_seconds: float
    checks: dict[str, Any] = {}


class ReadinessStatus(BaseModel):
    """Readiness check response model."""

    ready: bool
    checks: dict[str, bool]


class LivenessStatus(BaseModel):
    """Liveness check response model."""

    alive: bool
    timestamp: float


@router.get("/health", response_model=HealthStatus)
async def health_check() -> HealthStatus:
    """
    General health check endpoint.
    
    Returns basic health information about the service.
    """
    return HealthStatus(
        status="healthy",
        uptime_seconds=time.time() - _start_time,
    )


@router.get("/health/ready", response_model=ReadinessStatus)
async def readiness_check(
    response: Response,
    settings: Settings = Depends(get_settings),
) -> ReadinessStatus:
    """
    Readiness probe for Kubernetes.
    
    Checks if the service is ready to accept traffic.
    Returns 503 if any critical dependency is not ready.
    """
    checks: dict[str, bool] = {}
    
    # Check database connectivity
    try:
        async for db in get_db():
            await db.execute("SELECT 1")
            checks["database"] = True
            break
    except Exception:
        checks["database"] = False

    # Add more readiness checks as needed
    checks["config"] = bool(settings.jwt_secret)

    all_ready = all(checks.values())
    
    if not all_ready:
        response.status_code = 503

    return ReadinessStatus(ready=all_ready, checks=checks)


@router.get("/health/live", response_model=LivenessStatus)
async def liveness_check() -> LivenessStatus:
    """
    Liveness probe for Kubernetes.
    
    Basic check to verify the service process is running.
    If this fails, Kubernetes should restart the pod.
    """
    return LivenessStatus(alive=True, timestamp=time.time())


@router.get("/health/startup")
async def startup_check(response: Response) -> dict[str, Any]:
    """
    Startup probe for Kubernetes.
    
    Used during initial startup to allow slow-starting containers.
    """
    uptime = time.time() - _start_time
    
    # Consider started after basic initialization
    started = uptime > 1.0
    
    if not started:
        response.status_code = 503
    
    return {
        "started": started,
        "uptime_seconds": uptime,
    }
