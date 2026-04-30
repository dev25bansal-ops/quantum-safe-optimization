"""
Health check endpoints for Kubernetes and monitoring.

Provides:
- Liveness probe: Is the service alive?
- Readiness probe: Can the service accept traffic?
- Detailed health: Full system status with dependencies
"""

import asyncio
import os
import time
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from enum import Enum
from typing import Any

import redis.asyncio as redis
from fastapi import APIRouter, Response, status

router = APIRouter()


class HealthStatus(str, Enum):
    """Health check status values."""

    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"


@dataclass
class ComponentHealth:
    """Health status of a single component."""

    name: str
    status: HealthStatus
    latency_ms: float | None = None
    message: str | None = None
    details: dict[str, Any] = field(default_factory=dict)


@dataclass
class SystemHealth:
    """Overall system health status."""

    status: HealthStatus
    version: str
    environment: str
    timestamp: str
    uptime_seconds: float
    components: dict[str, dict[str, Any]] = field(default_factory=dict)


# Track service start time
_service_start_time: datetime | None = None


def get_uptime() -> float:
    """Get service uptime in seconds."""
    global _service_start_time
    if _service_start_time is None:
        _service_start_time = datetime.now(UTC)
    return (datetime.now(UTC) - _service_start_time).total_seconds()


async def check_cosmos_health() -> ComponentHealth:
    """Check Cosmos DB connection health."""
    try:
        from api.db.cosmos import cosmos_manager

        start = datetime.now(UTC)
        health_status = await cosmos_manager.health_check()
        latency = (datetime.now(UTC) - start).total_seconds() * 1000

        if health_status.healthy:
            return ComponentHealth(
                name="cosmos_db",
                status=HealthStatus.HEALTHY,
                latency_ms=round(health_status.latency_ms, 2),
                details={
                    "endpoint": health_status.details.get("endpoint", ""),
                    "database": health_status.details.get("database", ""),
                    "circuit_breaker": health_status.details.get("circuit_breaker", {}),
                },
            )
        else:
            return ComponentHealth(
                name="cosmos_db",
                status=HealthStatus.UNHEALTHY,
                latency_ms=round(latency, 2),
                message=health_status.error,
                details=health_status.details,
            )
    except Exception as e:
        return ComponentHealth(
            name="cosmos_db",
            status=HealthStatus.UNHEALTHY,
            message=str(e),
        )


async def check_redis_health() -> ComponentHealth:
    """Check Redis connection health."""
    redis_url = os.getenv("REDIS_URL", "redis://localhost:6379")

    try:
        start = datetime.now(UTC)
        client = redis.from_url(redis_url, decode_responses=True)

        # Ping Redis
        await client.ping()

        # Get some stats
        info = await client.info("server")
        latency = (datetime.now(UTC) - start).total_seconds() * 1000

        await client.close()

        return ComponentHealth(
            name="redis",
            status=HealthStatus.HEALTHY,
            latency_ms=round(latency, 2),
            details={
                "version": info.get("redis_version", "unknown"),
                "connected_clients": info.get("connected_clients", 0),
            },
        )
    except Exception as e:
        return ComponentHealth(
            name="redis",
            status=HealthStatus.UNHEALTHY,
            message=str(e),
        )


async def check_crypto_health() -> ComponentHealth:
    """Check PQC crypto module health."""
    try:
        import quantum_safe_crypto as pqc

        start = datetime.now(UTC)

        # Quick test of crypto operations
        kem_keys = pqc.KemKeyPair()
        sign_keys = pqc.SigningKeyPair()

        # Test encryption/decryption
        ct, ss1 = pqc.py_kem_encapsulate(kem_keys.public_key)
        ss2 = pqc.py_kem_decapsulate(ct, kem_keys.secret_key)

        # Test signing/verification
        msg = b"health_check"
        sig = sign_keys.sign(msg)
        valid = sign_keys.verify(msg, sig)

        latency = (datetime.now(UTC) - start).total_seconds() * 1000

        if ss1 == ss2 and valid:
            # Get supported levels
            levels = pqc.py_get_supported_levels()
            return ComponentHealth(
                name="pqc_crypto",
                status=HealthStatus.HEALTHY,
                latency_ms=round(latency, 2),
                details={
                    "kem_algorithm": kem_keys.algorithm,
                    "signing_algorithm": sign_keys.algorithm,
                    "supported_levels": [level[0] for level in levels],
                },
            )
        else:
            return ComponentHealth(
                name="pqc_crypto",
                status=HealthStatus.UNHEALTHY,
                message="Crypto verification failed",
            )
    except ImportError:
        return ComponentHealth(
            name="pqc_crypto",
            status=HealthStatus.UNHEALTHY,
            message="quantum_safe_crypto module not available",
        )
    except Exception as e:
        return ComponentHealth(
            name="pqc_crypto",
            status=HealthStatus.UNHEALTHY,
            message=str(e),
        )


async def check_secrets_health() -> ComponentHealth:
    """Check secrets manager health."""
    try:
        from api.security.secrets_manager import SecretsManager

        start = datetime.now(UTC)
        manager = SecretsManager.get_instance()

        # Try to get a known secret (JWT secret should always exist)
        jwt_secret = await manager.get_secret("jwt-secret", fallback="default")

        latency = (datetime.now(UTC) - start).total_seconds() * 1000

        return ComponentHealth(
            name="secrets_manager",
            status=HealthStatus.HEALTHY,
            latency_ms=round(latency, 2),
            details={
                "using_keyvault": manager.is_using_keyvault,
                "has_jwt_secret": jwt_secret is not None,
            },
        )
    except Exception as e:
        return ComponentHealth(
            name="secrets_manager",
            status=HealthStatus.DEGRADED,
            message=str(e),
        )


def determine_overall_status(components: list[ComponentHealth]) -> HealthStatus:
    """Determine overall health based on component statuses."""
    statuses = [c.status for c in components]

    if all(s == HealthStatus.HEALTHY for s in statuses):
        return HealthStatus.HEALTHY
    elif any(s == HealthStatus.UNHEALTHY for s in statuses):
        # Check if critical components are unhealthy
        critical = {"cosmos_db", "pqc_crypto"}
        for comp in components:
            if comp.name in critical and comp.status == HealthStatus.UNHEALTHY:
                return HealthStatus.UNHEALTHY
        return HealthStatus.DEGRADED
    else:
        return HealthStatus.DEGRADED


@router.get("/health")
async def health_check() -> dict[str, Any]:
    """
    Basic health check endpoint.

    Returns service status and version information.
    Quick response for load balancer health checks.
    """
    return {
        "status": "healthy",
        "timestamp": datetime.now(UTC).isoformat(),
        "version": os.getenv("APP_VERSION", "0.1.0"),
        "environment": os.getenv("APP_ENV", "development"),
    }


@router.get("/health/ready")
async def readiness_check(response: Response) -> dict[str, Any]:
    """
    Kubernetes readiness probe.

    Checks if the service is ready to accept traffic.
    All critical dependencies must be available.
    """
    # Run health checks in parallel
    cosmos_task = asyncio.create_task(check_cosmos_health())
    redis_task = asyncio.create_task(check_redis_health())
    crypto_task = asyncio.create_task(check_crypto_health())

    # Wait for all checks (with timeout)
    try:
        results = await asyncio.wait_for(
            asyncio.gather(cosmos_task, redis_task, crypto_task, return_exceptions=True),
            timeout=10.0,
        )
    except TimeoutError:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        return {
            "ready": False,
            "reason": "Health checks timed out",
            "timestamp": datetime.now(UTC).isoformat(),
        }

    # Process results
    components = {}
    all_ready = True

    for result in results:
        if isinstance(result, Exception):
            all_ready = False
            continue

        components[result.name] = {
            "status": result.status.value,
            "latency_ms": result.latency_ms,
            "message": result.message,
        }

        # Critical components must be healthy
        if result.name in {"cosmos_db", "pqc_crypto"}:
            if result.status != HealthStatus.HEALTHY:
                all_ready = False

    if not all_ready:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE

    return {
        "ready": all_ready,
        "components": components,
        "timestamp": datetime.now(UTC).isoformat(),
    }


@router.get("/health/live")
async def liveness_check() -> dict[str, str]:
    """
    Kubernetes liveness probe.

    Simple check that the service is alive and responsive.
    Should always return quickly without checking dependencies.
    """
    return {
        "status": "alive",
        "timestamp": datetime.now(UTC).isoformat(),
    }


@router.get("/health/detailed")
async def detailed_health_check(response: Response) -> dict[str, Any]:
    """
    Detailed health check with all component statuses.

    Provides comprehensive system health information for monitoring
    and debugging. Not suitable for frequent polling.
    """
    # Run all health checks in parallel
    checks = await asyncio.gather(
        check_cosmos_health(),
        check_redis_health(),
        check_crypto_health(),
        check_secrets_health(),
        return_exceptions=True,
    )

    # Process results
    components = []
    for result in checks:
        if isinstance(result, Exception):
            components.append(
                ComponentHealth(
                    name="unknown",
                    status=HealthStatus.UNHEALTHY,
                    message=str(result),
                )
            )
        else:
            components.append(result)

    # Determine overall status
    overall_status = determine_overall_status(components)

    # Set response status code
    if overall_status == HealthStatus.UNHEALTHY:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    elif overall_status == HealthStatus.DEGRADED:
        response.status_code = status.HTTP_200_OK  # Still operational

    # Build response
    health = SystemHealth(
        status=overall_status,
        version=os.getenv("APP_VERSION", "0.1.0"),
        environment=os.getenv("APP_ENV", "development"),
        timestamp=datetime.now(UTC).isoformat(),
        uptime_seconds=round(get_uptime(), 2),
        components={
            comp.name: {
                "status": comp.status.value,
                "latency_ms": comp.latency_ms,
                "message": comp.message,
                "details": comp.details,
            }
            for comp in components
        },
    )

    return asdict(health)


@router.get("/health/crypto")
async def crypto_health() -> dict[str, Any]:
    """
    Post-Quantum Cryptography status endpoint.

    Returns algorithm details, sizes, supported levels, and health status.
    """
    start = time.perf_counter()
    try:
        import quantum_safe_crypto as pqc

        kem_keys = pqc.KemKeyPair()
        sign_keys = pqc.SigningKeyPair()

        # Quick verification
        ct, ss1 = pqc.py_kem_encapsulate(kem_keys.public_key)
        ss2 = pqc.py_kem_decapsulate(ct, kem_keys.secret_key)

        msg = b"pqc_status"
        sig = sign_keys.sign(msg)
        valid = sign_keys.verify(msg, sig)

        latency_ms = (time.perf_counter() - start) * 1000

        if ss1 != ss2 or not valid:
            return {
                "status": "unhealthy",
                "timestamp": datetime.now(UTC).isoformat(),
                "error": "Crypto verification failed",
            }

        supported_levels = pqc.py_get_supported_levels()

        return {
            "status": "healthy",
            "timestamp": datetime.now(UTC).isoformat(),
            "latency_ms": round(latency_ms, 2),
            "algorithms": {
                "kem": {
                    "name": kem_keys.algorithm,
                    "public_key_size": len(kem_keys.public_key),
                    "secret_key_size": len(kem_keys.secret_key),
                    "ciphertext_size": len(ct),
                },
                "signature": {
                    "name": sign_keys.algorithm,
                    "public_key_size": len(sign_keys.public_key),
                    "secret_key_size": len(sign_keys.secret_key),
                    "signature_size": len(sig),
                },
            },
            "supported_levels": [level[0] for level in supported_levels],
        }
    except Exception as e:
        return {
            "status": "unhealthy",
            "timestamp": datetime.now(UTC).isoformat(),
            "error": str(e),
        }
