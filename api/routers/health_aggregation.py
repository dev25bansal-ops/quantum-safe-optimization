"""
Health Check Aggregation Endpoints.

Provides consolidated health status across all services:
- Aggregated system health
- Dependency health status
- Health check history
- Alert thresholds
"""

import asyncio
import logging
from collections import deque
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime, timedelta
from enum import Enum
from typing import Any

from fastapi import APIRouter, Query, Response, status

logger = logging.getLogger(__name__)

router = APIRouter()


class HealthStatus(str, Enum):
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"


@dataclass
class ComponentHealth:
    name: str
    status: HealthStatus
    latency_ms: float | None = None
    message: str | None = None
    details: dict[str, Any] = field(default_factory=dict)
    last_check: str | None = None


@dataclass
class AggregatedHealth:
    status: HealthStatus
    components: dict[str, dict[str, Any]]
    summary: dict[str, int]
    uptime_seconds: float
    timestamp: str


_health_history: deque = deque(maxlen=1000)
_start_time: datetime = datetime.now(UTC)
_component_cache: dict[str, ComponentHealth] = {}


async def check_cosmos_db() -> ComponentHealth:
    """Check Cosmos DB health."""
    try:
        from api.db.cosmos import cosmos_manager

        start = datetime.now(UTC)
        health_status = await cosmos_manager.health_check()
        latency = (datetime.now(UTC) - start).total_seconds() * 1000

        return ComponentHealth(
            name="cosmos_db",
            status=HealthStatus.HEALTHY if health_status.healthy else HealthStatus.UNHEALTHY,
            latency_ms=round(latency, 2),
            message=health_status.error if not health_status.healthy else None,
            details=health_status.details or {},
            last_check=datetime.now(UTC).isoformat(),
        )
    except Exception as e:
        return ComponentHealth(
            name="cosmos_db",
            status=HealthStatus.UNHEALTHY,
            message=str(e),
            last_check=datetime.now(UTC).isoformat(),
        )


async def check_redis() -> ComponentHealth:
    """Check Redis health."""
    import os

    try:
        import redis.asyncio as redis

        redis_url = os.getenv("REDIS_URL", "redis://localhost:6379")
        start = datetime.now(UTC)
        client = redis.from_url(redis_url, decode_responses=True)
        await client.ping()
        info = await client.info("server")
        latency = (datetime.now(UTC) - start).total_seconds() * 1000
        await client.close()

        return ComponentHealth(
            name="redis",
            status=HealthStatus.HEALTHY,
            latency_ms=round(latency, 2),
            details={"version": info.get("redis_version", "unknown")},
            last_check=datetime.now(UTC).isoformat(),
        )
    except Exception as e:
        return ComponentHealth(
            name="redis",
            status=HealthStatus.UNHEALTHY,
            message=str(e),
            last_check=datetime.now(UTC).isoformat(),
        )


async def check_crypto() -> ComponentHealth:
    """Check PQC crypto module health."""
    try:
        import quantum_safe_crypto as pqc

        start = datetime.now(UTC)

        kem_keys = pqc.KemKeyPair()
        sign_keys = pqc.SigningKeyPair()

        ct, ss1 = pqc.py_kem_encapsulate(kem_keys.public_key)
        ss2 = pqc.py_kem_decapsulate(ct, kem_keys.secret_key)

        msg = b"health_check"
        sig = sign_keys.sign(msg)
        valid = sign_keys.verify(msg, sig)

        latency = (datetime.now(UTC) - start).total_seconds() * 1000

        if ss1 == ss2 and valid:
            return ComponentHealth(
                name="pqc_crypto",
                status=HealthStatus.HEALTHY,
                latency_ms=round(latency, 2),
                details={
                    "kem_algorithm": kem_keys.algorithm,
                    "signing_algorithm": sign_keys.algorithm,
                },
                last_check=datetime.now(UTC).isoformat(),
            )
        return ComponentHealth(
            name="pqc_crypto",
            status=HealthStatus.UNHEALTHY,
            message="Crypto verification failed",
            last_check=datetime.now(UTC).isoformat(),
        )
    except ImportError:
        return ComponentHealth(
            name="pqc_crypto",
            status=HealthStatus.DEGRADED,
            message="quantum_safe_crypto not available",
            last_check=datetime.now(UTC).isoformat(),
        )
    except Exception as e:
        return ComponentHealth(
            name="pqc_crypto",
            status=HealthStatus.UNHEALTHY,
            message=str(e),
            last_check=datetime.now(UTC).isoformat(),
        )


async def check_secrets_manager() -> ComponentHealth:
    """Check secrets manager health."""
    try:
        from api.security.secrets_manager import SecretsManager

        start = datetime.now(UTC)
        manager = SecretsManager.get_instance()
        await manager.get_secret("jwt-secret", fallback="default")
        latency = (datetime.now(UTC) - start).total_seconds() * 1000

        return ComponentHealth(
            name="secrets_manager",
            status=HealthStatus.HEALTHY,
            latency_ms=round(latency, 2),
            details={"using_keyvault": manager.is_using_keyvault},
            last_check=datetime.now(UTC).isoformat(),
        )
    except Exception as e:
        return ComponentHealth(
            name="secrets_manager",
            status=HealthStatus.DEGRADED,
            message=str(e),
            last_check=datetime.now(UTC).isoformat(),
        )


async def check_rate_limiter() -> ComponentHealth:
    """Check rate limiter health."""
    try:
        from api.security.rate_limiter import limiter

        return ComponentHealth(
            name="rate_limiter",
            status=HealthStatus.HEALTHY,
            details={"enabled": True},
            last_check=datetime.now(UTC).isoformat(),
        )
    except Exception as e:
        return ComponentHealth(
            name="rate_limiter",
            status=HealthStatus.DEGRADED,
            message=str(e),
            last_check=datetime.now(UTC).isoformat(),
        )


async def check_scheduler() -> ComponentHealth:
    """Check scheduler health."""
    try:
        from api.routers.scheduling import scheduler

        return ComponentHealth(
            name="scheduler",
            status=HealthStatus.HEALTHY
            if scheduler and scheduler.running
            else HealthStatus.DEGRADED,
            details={"running": scheduler.running if scheduler else False},
            last_check=datetime.now(UTC).isoformat(),
        )
    except Exception as e:
        return ComponentHealth(
            name="scheduler",
            status=HealthStatus.DEGRADED,
            message=str(e),
            last_check=datetime.now(UTC).isoformat(),
        )


def _determine_overall_status(components: list[ComponentHealth]) -> HealthStatus:
    """Determine overall health based on component statuses."""
    statuses = [c.status for c in components]

    if all(s == HealthStatus.HEALTHY for s in statuses):
        return HealthStatus.HEALTHY

    critical = {"cosmos_db", "pqc_crypto"}
    for comp in components:
        if comp.name in critical and comp.status == HealthStatus.UNHEALTHY:
            return HealthStatus.UNHEALTHY

    if any(s == HealthStatus.UNHEALTHY for s in statuses):
        return HealthStatus.DEGRADED

    return HealthStatus.DEGRADED


@router.get("/")
async def get_aggregated_health(
    response: Response,
    include_details: bool = Query(default=True),
) -> dict[str, Any]:
    """Get aggregated health status of all components."""
    checks = await asyncio.gather(
        check_cosmos_db(),
        check_redis(),
        check_crypto(),
        check_secrets_manager(),
        check_rate_limiter(),
        check_scheduler(),
        return_exceptions=True,
    )

    components = []
    for result in checks:
        if isinstance(result, Exception):
            components.append(
                ComponentHealth(
                    name="unknown",
                    status=HealthStatus.UNHEALTHY,
                    message=str(result),
                    last_check=datetime.now(UTC).isoformat(),
                )
            )
        else:
            components.append(result)
            _component_cache[result.name] = result

    overall_status = _determine_overall_status(components)

    if overall_status == HealthStatus.UNHEALTHY:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE

    summary = {
        "healthy": sum(1 for c in components if c.status == HealthStatus.HEALTHY),
        "degraded": sum(1 for c in components if c.status == HealthStatus.DEGRADED),
        "unhealthy": sum(1 for c in components if c.status == HealthStatus.UNHEALTHY),
    }

    health_record = {
        "timestamp": datetime.now(UTC).isoformat(),
        "status": overall_status.value,
        "summary": summary,
    }
    _health_history.append(health_record)

    component_data = {}
    for comp in components:
        data = {
            "status": comp.status.value,
            "latency_ms": comp.latency_ms,
        }
        if include_details:
            data["message"] = comp.message
            data["details"] = comp.details
            data["last_check"] = comp.last_check
        component_data[comp.name] = data

    return {
        "status": overall_status.value,
        "components": component_data,
        "summary": summary,
        "uptime_seconds": (datetime.now(UTC) - _start_time).total_seconds(),
        "timestamp": datetime.now(UTC).isoformat(),
    }


@router.get("/component/{component_name}")
async def get_component_health(component_name: str, response: Response) -> dict[str, Any]:
    """Get health status of a specific component."""
    check_funcs = {
        "cosmos_db": check_cosmos_db,
        "redis": check_redis,
        "pqc_crypto": check_crypto,
        "secrets_manager": check_secrets_manager,
        "rate_limiter": check_rate_limiter,
        "scheduler": check_scheduler,
    }

    if component_name not in check_funcs:
        response.status_code = status.HTTP_404_NOT_FOUND
        return {"error": f"Unknown component: {component_name}"}

    health = await check_funcs[component_name]()

    if health.status == HealthStatus.UNHEALTHY:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE

    return asdict(health)


@router.get("/history")
async def get_health_history(
    hours: int = Query(default=1, ge=1, le=24),
) -> dict[str, Any]:
    """Get health check history."""
    cutoff = datetime.now(UTC) - timedelta(hours=hours)

    history = [h for h in _health_history if datetime.fromisoformat(h["timestamp"]) > cutoff]

    return {
        "total_checks": len(history),
        "history": list(history),
        "timestamp": datetime.now(UTC).isoformat(),
    }


@router.get("/trends")
async def get_health_trends(
    hours: int = Query(default=24, ge=1, le=168),
) -> dict[str, Any]:
    """Get health trends over time."""
    cutoff = datetime.now(UTC) - timedelta(hours=hours)

    history = [h for h in _health_history if datetime.fromisoformat(h["timestamp"]) > cutoff]

    if not history:
        return {
            "trends": {},
            "timestamp": datetime.now(UTC).isoformat(),
        }

    status_counts = {"healthy": 0, "degraded": 0, "unhealthy": 0}
    for h in history:
        status_counts[h["status"]] = status_counts.get(h["status"], 0) + 1

    total = len(history)
    availability = (status_counts.get("healthy", 0) / total * 100) if total > 0 else 100.0

    return {
        "total_checks": total,
        "availability_percent": round(availability, 2),
        "status_distribution": status_counts,
        "component_trends": {
            name: {"status": comp.status.value, "latency_ms": comp.latency_ms}
            for name, comp in _component_cache.items()
        },
        "timestamp": datetime.now(UTC).isoformat(),
    }


@router.get("/ready")
async def readiness_check(response: Response) -> dict[str, Any]:
    """Kubernetes readiness probe - check critical dependencies."""
    critical_checks = await asyncio.gather(
        check_cosmos_db(),
        check_crypto(),
        return_exceptions=True,
    )

    all_ready = True
    components = {}

    for result in critical_checks:
        if isinstance(result, Exception):
            all_ready = False
            continue

        components[result.name] = {
            "status": result.status.value,
            "latency_ms": result.latency_ms,
        }

        if result.status == HealthStatus.UNHEALTHY:
            all_ready = False

    if not all_ready:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE

    return {
        "ready": all_ready,
        "components": components,
        "timestamp": datetime.now(UTC).isoformat(),
    }


@router.get("/live")
async def liveness_check() -> dict[str, str]:
    """Kubernetes liveness probe - basic alive check."""
    return {
        "status": "alive",
        "uptime_seconds": str((datetime.now(UTC) - _start_time).total_seconds()),
        "timestamp": datetime.now(UTC).isoformat(),
    }
