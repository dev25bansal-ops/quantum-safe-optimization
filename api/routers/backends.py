"""
Quantum Backend Management API Router

Provides endpoints for managing quantum computing backend connections,
monitoring health status, and retrieving available devices.
"""

import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field

from api.routers.auth import get_current_user
from api.security.rate_limiter import RateLimits, limiter

# Import backend components
from optimization.src.backends import (
    BackendConnectionManager,
    BackendType,
    get_connection_manager,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/backends", tags=["backends"])


# ============================================================================
# Response Models
# ============================================================================


class BackendInfo(BaseModel):
    """Information about a quantum backend provider."""

    type: str = Field(..., description="Backend type identifier")
    status: str = Field(..., description="Current health status")
    configured: bool = Field(..., description="Whether credentials are configured")

    class Config:
        json_schema_extra = {
            "example": {
                "type": "ibm_quantum",
                "status": "healthy",
                "configured": True,
            }
        }


class DeviceInfo(BaseModel):
    """Information about a quantum device."""

    name: str = Field(..., description="Device name or identifier")
    provider: str | None = Field(None, description="Hardware provider")
    num_qubits: int | None = Field(None, description="Number of qubits")
    status: str | None = Field(None, description="Device operational status")
    device_type: str | None = Field(None, description="Device type (QPU, simulator)")
    region: str | None = Field(None, description="Geographic region")
    cost_per_shot: float | None = Field(None, description="Approximate cost per shot")

    class Config:
        json_schema_extra = {
            "example": {
                "name": "ibm_brisbane",
                "provider": "IBM",
                "num_qubits": 127,
                "status": "operational",
                "device_type": "qpu",
            }
        }


class BackendMetrics(BaseModel):
    """Connection metrics for a backend."""

    backend_type: str
    status: str
    pool_size: int
    active_connections: int
    total_requests: int
    successful_requests: int
    failed_requests: int
    success_rate: float
    average_latency_ms: float
    last_error: str | None = None


class BackendListResponse(BaseModel):
    """Response containing list of available backends."""

    backends: list[BackendInfo]
    message: str = "Available quantum computing backends"


class DeviceListResponse(BaseModel):
    """Response containing list of devices for a backend."""

    backend_type: str
    devices: list[dict[str, Any]]
    total: int


class MetricsResponse(BaseModel):
    """Response containing backend metrics."""

    metrics: dict[str, BackendMetrics]


class ConnectionTestResult(BaseModel):
    """Result of testing a backend connection."""

    backend_type: str
    success: bool
    message: str
    latency_ms: float | None = None
    devices_found: int | None = None


# ============================================================================
# Helper Functions
# ============================================================================


def _get_manager() -> BackendConnectionManager:
    """Get the backend connection manager."""
    return get_connection_manager()


def _backend_type_from_string(backend_str: str) -> BackendType:
    """Convert string to BackendType enum."""
    backend_map = {
        "ibm_quantum": BackendType.IBM_QUANTUM,
        "ibm": BackendType.IBM_QUANTUM,
        "aws_braket": BackendType.AWS_BRAKET,
        "aws": BackendType.AWS_BRAKET,
        "braket": BackendType.AWS_BRAKET,
        "azure_quantum": BackendType.AZURE_QUANTUM,
        "azure": BackendType.AZURE_QUANTUM,
        "dwave": BackendType.DWAVE,
        "d-wave": BackendType.DWAVE,
        "local_simulator": BackendType.LOCAL_SIMULATOR,
        "local": BackendType.LOCAL_SIMULATOR,
        "simulator": BackendType.LOCAL_SIMULATOR,
    }

    backend_lower = backend_str.lower().replace("-", "_")
    if backend_lower in backend_map:
        return backend_map[backend_lower]

    # Try direct enum value
    try:
        return BackendType(backend_str)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unknown backend type: {backend_str}. "
            f"Valid types: {[t.value for t in BackendType]}",
        ) from e


# ============================================================================
# Endpoints
# ============================================================================


@router.get("", response_model=BackendListResponse)
async def list_backends(
    current_user: dict = Depends(get_current_user),
):
    """
    List all available quantum computing backends.

    Returns information about each backend including:
    - Backend type identifier
    - Current health status
    - Whether credentials are configured
    """
    manager = _get_manager()
    backends = manager.get_available_backends()

    return BackendListResponse(
        backends=[BackendInfo(**b) for b in backends],
        message=f"Found {len(backends)} quantum backends",
    )


@router.get("/{backend_type}/status")
async def get_backend_status(
    backend_type: str,
    current_user: dict = Depends(get_current_user),
):
    """
    Get detailed status for a specific backend.

    Returns connection pool status, health state, and recent metrics.
    """
    bt = _backend_type_from_string(backend_type)
    manager = _get_manager()

    metrics = manager.get_metrics(bt)
    provider_status = manager.get_provider_status(bt)

    return {
        "backend_type": bt.value,
        "status": provider_status.value,
        "metrics": metrics,
    }


@router.get("/{backend_type}/devices", response_model=DeviceListResponse)
async def list_devices(
    backend_type: str,
    current_user: dict = Depends(get_current_user),
):
    """
    List available devices for a specific backend.

    Returns all quantum devices/targets available through this backend,
    including simulators and real quantum hardware.
    """
    bt = _backend_type_from_string(backend_type)
    manager = _get_manager()

    try:
        # Get a connection to fetch devices
        if not manager._running:
            await manager.start()

        backend = await manager.get_connection(bt)
        try:
            devices = await backend.get_available_devices()
            return DeviceListResponse(
                backend_type=bt.value,
                devices=devices,
                total=len(devices),
            )
        finally:
            await manager.release_connection(backend, success=True)

    except ConnectionError as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Cannot connect to {bt.value}: {str(e)}",
        ) from e
    except Exception as e:
        logger.error(f"Error listing devices for {bt.value}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error fetching devices: {str(e)}",
        ) from e


@router.post("/{backend_type}/test", response_model=ConnectionTestResult)
@limiter.limit(RateLimits.WRITE_OPERATIONS)
async def test_backend_connection(
    request: Request,
    backend_type: str,
    current_user: dict = Depends(get_current_user),
):
    """
    Test connection to a quantum backend.

    Attempts to establish a connection and fetch available devices.
    Returns success status, latency, and number of devices found.
    """
    from datetime import datetime

    bt = _backend_type_from_string(backend_type)
    manager = _get_manager()

    start_time = datetime.utcnow()

    try:
        if not manager._running:
            await manager.start()

        backend = await manager.get_connection(bt)
        try:
            devices = await backend.get_available_devices()
            elapsed = (datetime.utcnow() - start_time).total_seconds() * 1000

            return ConnectionTestResult(
                backend_type=bt.value,
                success=True,
                message=f"Successfully connected to {bt.value}",
                latency_ms=round(elapsed, 2),
                devices_found=len(devices),
            )
        finally:
            await manager.release_connection(backend, success=True)

    except ConnectionError as e:
        elapsed = (datetime.utcnow() - start_time).total_seconds() * 1000
        return ConnectionTestResult(
            backend_type=bt.value,
            success=False,
            message=f"Connection failed: {str(e)}",
            latency_ms=round(elapsed, 2),
        )
    except Exception as e:
        elapsed = (datetime.utcnow() - start_time).total_seconds() * 1000
        return ConnectionTestResult(
            backend_type=bt.value,
            success=False,
            message=f"Error: {str(e)}",
            latency_ms=round(elapsed, 2),
        )


@router.get("/metrics", response_model=MetricsResponse)
async def get_all_metrics(
    current_user: dict = Depends(get_current_user),
):
    """
    Get connection metrics for all backends.

    Returns pool sizes, request counts, success rates, and latency
    information for each configured backend.
    """
    manager = _get_manager()
    all_metrics = manager.get_metrics()

    return MetricsResponse(metrics={k: BackendMetrics(**v) for k, v in all_metrics.items()})


@router.post("/{backend_type}/refresh")
async def refresh_backend_cache(
    backend_type: str,
    current_user: dict = Depends(get_current_user),
):
    """
    Refresh cached device list for a backend.

    Forces a fresh query to the backend provider to update
    the list of available devices and their status.
    """
    bt = _backend_type_from_string(backend_type)
    manager = _get_manager()

    try:
        if not manager._running:
            await manager.start()

        backend = await manager.get_connection(bt)
        try:
            # Force refresh by calling get_available_devices
            devices = await backend.get_available_devices()
            return {
                "backend_type": bt.value,
                "message": "Cache refreshed successfully",
                "devices_found": len(devices),
            }
        finally:
            await manager.release_connection(backend, success=True)

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to refresh cache: {str(e)}",
        ) from e


@router.get("/health")
async def backends_health_check():
    """
    Health check for all quantum backends.

    Returns aggregated health status without requiring authentication.
    Useful for monitoring systems.
    """
    manager = _get_manager()

    health_status = {}
    for backend_type in BackendType:
        provider_status = manager.get_provider_status(backend_type)
        health_status[backend_type.value] = provider_status.value

    # Determine overall health
    statuses = list(health_status.values())
    if all(s == "healthy" for s in statuses if s != "unknown"):
        overall = "healthy"
    elif any(s == "unhealthy" for s in statuses):
        overall = "degraded"
    else:
        overall = "unknown"

    return {
        "status": overall,
        "backends": health_status,
    }


# ============================================================================
# Backend Configuration Endpoints
# ============================================================================


class BackendConfigRequest(BaseModel):
    """Request to configure a backend."""

    api_token: str | None = Field(None, description="API token for authentication")
    region: str | None = Field(None, description="Cloud region")
    device_name: str | None = Field(None, description="Default device to use")
    extra_config: dict[str, Any] | None = Field(default_factory=dict)


@router.post("/{backend_type}/configure")
async def configure_backend(
    backend_type: str,
    config: BackendConfigRequest,
    current_user: dict = Depends(get_current_user),
):
    """
    Configure credentials and settings for a backend.

    Note: For security, credentials are typically set via environment
    variables. This endpoint allows runtime configuration for testing.

    Admin role required.
    """
    # Check for admin role
    if "admin" not in current_user.get("roles", []):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin role required to configure backends",
        )

    bt = _backend_type_from_string(backend_type)
    manager = _get_manager()

    # Update credentials
    from optimization.src.backends.connection_manager import BackendCredentials

    creds = BackendCredentials(
        api_token=config.api_token,
        region=config.region,
        extra=config.extra_config or {},
    )

    manager._credentials[bt] = creds

    return {
        "backend_type": bt.value,
        "message": "Backend configured successfully",
        "configured": True,
    }
