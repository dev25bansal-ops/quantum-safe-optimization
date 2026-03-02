"""Health check endpoints for Kubernetes probes."""

from __future__ import annotations

import time
from typing import Any

from fastapi import APIRouter, Depends, Query, Response
from pydantic import BaseModel

from qsop.api.deps import Settings, get_db, get_settings

router = APIRouter()

_start_time = time.time()


class HealthStatus(BaseModel):
    """Health check response model."""

    status: str
    version: str = "1.0.0"
    uptime_seconds: float
    checks: dict[str, Any] = {}
    components: dict[str, Any] = {}
    ready: bool = True


class ReadinessStatus(BaseModel):
    """Readiness check response model."""

    ready: bool
    checks: dict[str, bool]


class LivenessStatus(BaseModel):
    """Liveness check response model."""

    alive: bool
    timestamp: float


@router.get("/health", response_model=HealthStatus)
async def health_check(
    detailed: bool = Query(False, description="Include detailed component health information"),
) -> HealthStatus:
    """
    General health check endpoint.

    Consolidates /health, /health/ready, and /health/detailed into a single endpoint
    to reduce frontend polling overhead.

    Args:
        detailed: When True, includes detailed component health information

    Returns:
        Health status including basic information and optionally detailed component checks
    """
    checks: dict[str, Any] = {}
    components: dict[str, Any] = {}

    if detailed:
        start_time = time.time()

        # Check database connectivity
        try:
            async for db in get_db():
                await db.execute("SELECT 1")
                db_latency_ms = (time.time() - start_time) * 1000
                components["database"] = {"status": "healthy", "latency_ms": db_latency_ms}
                checks["database"] = True
                break
        except Exception as e:
            components["database"] = {"status": "unhealthy", "latency_ms": None, "message": str(e)}
            checks["database"] = False

        # Add more component checks as needed
        if hasattr(router, "app") and router.app:
            settings = router.app.state.settings if hasattr(router.app.state, "settings") else None
            if settings:
                checks["config"] = bool(settings.jwt_secret)
                components["config"] = {"status": "healthy" if settings.jwt_secret else "degraded"}

        # Determine overall status based on components
        all_healthy = not any(c.get("status") == "unhealthy" for c in components.values())
        status = (
            "healthy"
            if all_healthy
            else "degraded"
            if any(c.get("status") == "degraded" for c in components.values())
            else "unhealthy"
        )

        return HealthStatus(
            status=status,
            uptime_seconds=time.time() - _start_time,
            checks=checks,
        )

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
    NOTE: Consider using /health?detailed=true instead for better performance.
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
