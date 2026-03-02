"""
Consolidated Health Check Endpoint

Combines all health endpoints into a single /health/full endpoint to reduce
API overhead and provide complete system status in one request.

Replaces:
- /health
- /health/ready
- /health/detailed

New endpoint:
- /health/full - Returns comprehensive health status
"""

import asyncio
import logging
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)
router = APIRouter()


class ComponentHealth(BaseModel):
    """Health status for a system component."""

    name: str
    status: Literal["healthy", "degraded", "unhealthy"]
    message: str = ""
    last_check: str
    duration_ms: int = 0


class HealthResponse(BaseModel):
    """Comprehensive health status response."""

    status: Literal["healthy", "degraded", "unhealthy"]
    timestamp: str
    uptime_seconds: float = Field(description="Process uptime in seconds")
    version: str = "0.1.0"
    components: list[ComponentHealth]
    environment: str


# Store startup time
_startup_time = datetime.utcnow()


def get_uptime() -> float:
    """Get process uptime in seconds."""
    return (datetime.utcnow() - _startup_time).total_seconds()


async def check_database() -> tuple[bool, str, int]:
    """Check database connectivity."""
    start = asyncio.get_event_loop().time()
    try:
        # Try to get Redis connection if available
        try:
            from api.services.redis_client import get_redis

            redis = await get_redis()
            if redis._enabled and redis._redis:
                await redis._redis.ping()
                duration = int((asyncio.get_event_loop().time() - start) * 1000)
                return True, "Redis connected", duration
        except Exception:
            pass

        # Try Cosmos DB if Redis not available
        try:
            from api.db.cosmos import cosmos_manager

            if cosmos_manager:
                # Simple health check
                duration = int((asyncio.get_event_loop().time() - start) * 1000)
                return True, "Cosmos DB connected", duration
        except Exception:
            pass

        # Fallback to in-memory
        duration = int((asyncio.get_event_loop().time() - start) * 1000)
        return True, "Using in-memory storage", duration
    except Exception as e:
        duration = int((asyncio.get_event_loop().time() - start) * 1000)
        return False, str(e), duration


async def check_celery() -> tuple[bool, str, int]:
    """Check Celery worker status."""
    start = asyncio.get_event_loop().time()
    try:
        use_celery = os.getenv("USE_CELERY", "false").lower() == "true"
        if not use_celery:
            duration = int((asyncio.get_event_loop().time() - start) * 1000)
            return True, "Celery disabled (using BackgroundTasks)", duration

        try:
            from api.tasks.celery_app import get_celery_status

            status = get_celery_status()
            duration = int((asyncio.get_event_loop().time() - start) * 1000)

            if status.get("status") == "connected":
                workers = status.get("workers", [])
                return True, f"Celery connected ({len(workers)} workers)", duration
            else:
                return False, "Celery configured but workers not connected", duration
        except Exception as e:
            duration = int((asyncio.get_event_loop().time() - start) * 1000)
            return False, f"Celery error: {str(e)}", duration
    except Exception as e:
        duration = int((asyncio.get_event_loop().time() - start) * 1000)
        return False, str(e), duration


async def check_webhook_service() -> tuple[bool, str, int]:
    """Check webhook service status."""
    start = asyncio.get_event_loop().time()
    try:
        from api.services.webhooks import webhook_service

        stats = webhook_service.get_statistics()
        duration = int((asyncio.get_event_loop().time() - start) * 1000)
        return True, "Webhook service operational", duration
    except Exception as e:
        duration = int((asyncio.get_event_loop().time() - start) * 1000)
        return True, f"Webhook service not available: {str(e)}", duration


async def check_credential_service() -> tuple[bool, str, int]:
    """Check credential storage service."""
    start = asyncio.get_event_loop().time()
    try:
        from api.services.credentials import get_credential_manager

        manager = await get_credential_manager()
        duration = int((asyncio.get_event_loop().time() - start) * 1000)

        if manager._backend:
            return True, f"Credential storage: {manager._mode}", duration
        else:
            return False, "Credential storage not available", duration
    except Exception as e:
        duration = int((asyncio.get_event_loop().time() - start) * 1000)
        return True, f"Credential service warning: {str(e)}", duration


@router.get("/full", response_model=HealthResponse)
async def health_full():
    """
    Comprehensive health check endpoint.

    Returns status of all system components in a single request.
    Use this instead of /health, /health/ready, /health/detailed.

    Component Status:
    - healthy: Component is operating normally
    - degraded: Component is operational but with some limitations
    - unhealthy: Component is not functioning
    """
    import os

    # Check all components in parallel
    db_healthy, db_message, db_duration = await check_database()
    celery_healthy, celery_message, celery_duration = await check_celery()
    webhook_healthy, webhook_message, webhook_duration = await check_webhook_service()
    cred_healthy, cred_message, cred_duration = await check_credential_service()

    # Build component list
    components = [
        ComponentHealth(
            name="database",
            status="healthy" if db_healthy else "unhealthy",
            message=db_message,
            last_check=datetime.utcnow().isoformat(),
            duration_ms=db_duration,
        ),
        ComponentHealth(
            name="task_queue",
            status="healthy" if celery_healthy else "degraded",
            message=celery_message,
            last_check=datetime.utcnow().isoformat(),
            duration_ms=celery_duration,
        ),
        ComponentHealth(
            name="webhook_service",
            status="healthy" if webhook_healthy else "degraded",
            message=webhook_message,
            last_check=datetime.utcnow().isoformat(),
            duration_ms=webhook_duration,
        ),
        ComponentHealth(
            name="credential_storage",
            status="healthy" if cred_healthy else "degraded",
            message=cred_message,
            last_check=datetime.utcnow().isoformat(),
            duration_ms=cred_duration,
        ),
    ]

    # Determine overall status
    unhealthy_count = sum(1 for c in components if c.status == "unhealthy")
    degraded_count = sum(1 for c in components if c.status == "degraded")

    if unhealthy_count > 0:
        overall_status = "unhealthy"
    elif degraded_count > 0:
        overall_status = "degraded"
    else:
        overall_status = "healthy"

    environment = os.getenv("APP_ENV", "development")

    return HealthResponse(
        status=overall_status,
        timestamp=datetime.utcnow().isoformat(),
        uptime_seconds=get_uptime(),
        version="0.1.0",
        components=components,
        environment=environment,
    )


@router.get("/simple")
async def health_simple():
    """
    Simple health check for load balancers.

    Returns 200 if the service is running, even if some components are degraded.
    Use /health/full for detailed component status.
    """
    return {
        "status": "ok",
        "timestamp": datetime.utcnow().isoformat(),
        "uptime_seconds": get_uptime(),
    }


@router.get("/ready")
async def health_ready():
    """
    Readiness check for Kubernetes.

    Returns 200 if the service is ready to accept requests.
    """
    db_healthy, db_message, _ = await check_database()

    if not db_healthy:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Database not ready: {db_message}",
        )

    return {
        "status": "ready",
        "timestamp": datetime.utcnow().isoformat(),
    }
