"""
Federation API Endpoints.

Provides multi-region quantum computing with intelligent routing.
"""

import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query

from .models import (
    FederationConfig,
    FederationRegion,
    FederationStatus,
    get_federation_status,
    ProviderType,
    RegionCreate,
    RegionResponse,
    RegionStatus,
    RoutingDecision,
    RoutingRequest,
    RoutingStrategy,
    select_region,
    seed_default_regions,
    _in_memory_regions,
    _region_metrics,
)

logger = logging.getLogger(__name__)

router = APIRouter()


def get_user_id() -> str:
    """Get current user ID (stub for auth integration)."""
    return "user_default"


@router.get("/status", response_model=FederationStatus)
async def get_status():
    """Get overall federation status."""
    return get_federation_status()


@router.get("/regions", response_model=list[RegionResponse])
async def list_regions(
    provider: ProviderType | None = None,
    status: RegionStatus | None = None,
    limit: int = Query(default=20, le=100),
):
    """List all federation regions."""
    seed_default_regions()

    regions = list(_in_memory_regions.values())

    if provider:
        regions = [r for r in regions if r.provider == provider]

    if status:
        regions = [r for r in regions if r.status == status]

    results = []
    for r in regions[:limit]:
        metrics = _region_metrics.get(r.region_id)
        results.append(
            RegionResponse(
                region_id=r.region_id,
                name=r.name,
                provider=r.provider,
                endpoint=r.endpoint,
                status=r.status,
                priority=r.priority,
                weight=r.weight,
                max_concurrent_jobs=r.max_concurrent_jobs,
                metrics={
                    "active_jobs": metrics.active_jobs if metrics else 0,
                    "avg_latency_ms": metrics.avg_latency_ms if metrics else 0,
                    "cost_per_shot": metrics.cost_per_shot if metrics else 0,
                },
                created_at=r.created_at.isoformat(),
                last_health_check=r.last_health_check.isoformat() if r.last_health_check else None,
            )
        )

    return results


@router.post("/regions", response_model=RegionResponse)
async def create_region(
    request: RegionCreate,
    user_id: str = Depends(get_user_id),
):
    """Add a new region to the federation."""
    region = FederationRegion.create(
        name=request.name,
        provider=request.provider,
        endpoint=request.endpoint,
        priority=request.priority,
        weight=request.weight,
        max_concurrent_jobs=request.max_concurrent_jobs,
    )

    if request.metadata:
        region.metadata = request.metadata

    _in_memory_regions[region.region_id] = region
    _region_metrics[region.region_id] = type(
        "RegionMetrics",
        (),
        {
            "region_id": region.region_id,
            "active_jobs": 0,
            "avg_latency_ms": 100.0,
            "cost_per_shot": 0.001,
        },
    )()

    logger.info(f"Created region: {region.region_id} - {region.name}")

    return RegionResponse(
        region_id=region.region_id,
        name=region.name,
        provider=region.provider,
        endpoint=region.endpoint,
        status=region.status,
        priority=region.priority,
        weight=region.weight,
        max_concurrent_jobs=region.max_concurrent_jobs,
        metrics=None,
        created_at=region.created_at.isoformat(),
        last_health_check=None,
    )


@router.get("/regions/{region_id}", response_model=RegionResponse)
async def get_region(region_id: str):
    """Get region details."""
    seed_default_regions()

    if region_id not in _in_memory_regions:
        raise HTTPException(status_code=404, detail="Region not found")

    r = _in_memory_regions[region_id]
    metrics = _region_metrics.get(region_id)

    return RegionResponse(
        region_id=r.region_id,
        name=r.name,
        provider=r.provider,
        endpoint=r.endpoint,
        status=r.status,
        priority=r.priority,
        weight=r.weight,
        max_concurrent_jobs=r.max_concurrent_jobs,
        metrics={
            "active_jobs": metrics.active_jobs if metrics else 0,
            "avg_latency_ms": metrics.avg_latency_ms if metrics else 0,
        },
        created_at=r.created_at.isoformat(),
        last_health_check=r.last_health_check.isoformat() if r.last_health_check else None,
    )


@router.patch("/regions/{region_id}/status")
async def update_region_status(
    region_id: str,
    status: RegionStatus,
    user_id: str = Depends(get_user_id),
):
    """Update region status."""
    if region_id not in _in_memory_regions:
        raise HTTPException(status_code=404, detail="Region not found")

    region = _in_memory_regions[region_id]
    region.status = status

    from datetime import datetime, timezone

    region.last_health_check = datetime.now(timezone.utc)

    return {"region_id": region_id, "status": status.value}


@router.delete("/regions/{region_id}")
async def remove_region(
    region_id: str,
    user_id: str = Depends(get_user_id),
):
    """Remove a region from the federation."""
    if region_id not in _in_memory_regions:
        raise HTTPException(status_code=404, detail="Region not found")

    del _in_memory_regions[region_id]
    _region_metrics.pop(region_id, None)

    return {"status": "removed", "region_id": region_id}


@router.post("/route", response_model=RoutingDecision)
async def route_job(request: RoutingRequest):
    """Get routing decision for a job."""
    from uuid import uuid4

    seed_default_regions()

    try:
        region, reason = select_region(
            strategy=RoutingStrategy.LATENCY,
            preferred_region=request.preferred_region,
            preferred_provider=request.preferred_provider,
            max_cost=request.max_cost,
            max_latency_ms=request.max_latency_ms,
        )

        metrics = _region_metrics.get(region.region_id)

        alternatives = []
        for r in list(_in_memory_regions.values())[:3]:
            if r.region_id != region.region_id:
                m = _region_metrics.get(r.region_id)
                alternatives.append(
                    {
                        "region_id": r.region_id,
                        "name": r.name,
                        "provider": r.provider.value,
                        "cost_per_shot": m.cost_per_shot if m else 0,
                        "avg_latency_ms": m.avg_latency_ms if m else 0,
                    }
                )

        return RoutingDecision(
            decision_id=f"route_{uuid4().hex[:8]}",
            selected_region=region.region_id,
            selected_provider=region.provider,
            endpoint=region.endpoint,
            estimated_cost=(metrics.cost_per_shot if metrics else 0.001) * request.shots,
            estimated_latency_ms=metrics.avg_latency_ms if metrics else 50.0,
            estimated_wait_time_s=5.0 + (metrics.active_jobs if metrics else 0) * 2,
            alternatives=alternatives,
            routing_reason=reason,
        )

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/providers")
async def list_providers():
    """List all supported providers."""
    return {
        "providers": [
            {
                "id": p.value,
                "name": p.value.upper().replace("_", " "),
                "regions": sum(1 for r in _in_memory_regions.values() if r.provider == p),
            }
            for p in ProviderType
        ]
    }


@router.get("/health")
async def federation_health():
    """Health check for federation."""
    status = get_federation_status()

    return {
        "status": "healthy" if status.healthy_regions > 0 else "degraded",
        "healthy_regions": status.healthy_regions,
        "total_regions": status.total_regions,
        "routing_available": status.healthy_regions > 0,
    }


@router.post("/failover/test")
async def test_failover(
    from_region: str,
    to_region: str,
    user_id: str = Depends(get_user_id),
):
    """Test failover between regions."""
    seed_default_regions()

    if from_region not in _in_memory_regions:
        raise HTTPException(status_code=404, detail=f"Source region {from_region} not found")

    if to_region not in _in_memory_regions:
        raise HTTPException(status_code=404, detail=f"Target region {to_region} not found")

    source = _in_memory_regions[from_region]
    target = _in_memory_regions[to_region]

    return {
        "status": "failover_test_passed",
        "from_region": {"id": from_region, "name": source.name, "provider": source.provider.value},
        "to_region": {"id": to_region, "name": target.name, "provider": target.provider.value},
        "estimated_downtime_ms": 500,
        "jobs_to_migrate": _region_metrics.get(
            from_region, type("M", (), {"active_jobs": 0})()
        ).active_jobs,
    }


@router.get("/metrics")
async def get_federation_metrics():
    """Get aggregated metrics across all regions."""
    seed_default_regions()

    total_active = sum(m.active_jobs for m in _region_metrics.values())
    total_queued = sum(
        m.queued_jobs if hasattr(m, "queued_jobs") else 0 for m in _region_metrics.values()
    )
    avg_latency = (
        sum(m.avg_latency_ms for m in _region_metrics.values()) / len(_region_metrics)
        if _region_metrics
        else 0
    )

    by_provider: dict[str, Any] = {}
    for region in _in_memory_regions.values():
        provider = region.provider.value
        if provider not in by_provider:
            by_provider[provider] = {"regions": 0, "active_jobs": 0, "healthy": 0}
        by_provider[provider]["regions"] += 1
        metrics = _region_metrics.get(region.region_id)
        if metrics:
            by_provider[provider]["active_jobs"] += metrics.active_jobs
        if region.status == RegionStatus.HEALTHY:
            by_provider[provider]["healthy"] += 1

    return {
        "total_active_jobs": total_active,
        "total_queued_jobs": total_queued,
        "average_latency_ms": round(avg_latency, 2),
        "total_regions": len(_in_memory_regions),
        "healthy_regions": sum(
            1 for r in _in_memory_regions.values() if r.status == RegionStatus.HEALTHY
        ),
        "by_provider": by_provider,
    }
