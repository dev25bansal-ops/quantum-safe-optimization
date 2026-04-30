"""
Federation Models for Multi-Region Quantum Computing.

Provides models for cross-region job routing, failover, and load balancing.
"""

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field


class RoutingStrategy(str, Enum):
    """Job routing strategies."""

    LATENCY = "latency"
    COST = "cost"
    LOAD_BALANCED = "load_balanced"
    FAILOVER = "failover"
    ROUND_ROBIN = "round_robin"
    PRIORITY = "priority"
    REGION_AFFINITY = "region_affinity"


class RegionStatus(str, Enum):
    """Region operational status."""

    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    OFFLINE = "offline"
    MAINTENANCE = "maintenance"


class ProviderType(str, Enum):
    """Quantum provider types."""

    IBM = "ibm"
    AWS = "aws"
    AZURE = "azure"
    DWAVE = "dwave"
    GOOGLE = "google"
    LOCAL = "local"


@dataclass
class FederationRegion:
    """A region in the federation."""

    region_id: str
    name: str
    provider: ProviderType
    endpoint: str
    status: RegionStatus = RegionStatus.HEALTHY
    priority: int = 1
    weight: int = 100
    max_concurrent_jobs: int = 10
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    last_health_check: datetime | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def create(
        cls,
        name: str,
        provider: ProviderType,
        endpoint: str,
        priority: int = 1,
        **kwargs,
    ) -> "FederationRegion":
        """Create a new federation region."""
        region_id = f"region_{uuid4().hex[:8]}"
        return cls(
            region_id=region_id,
            name=name,
            provider=provider,
            endpoint=endpoint,
            priority=priority,
            metadata=kwargs,
        )


@dataclass
class RegionMetrics:
    """Metrics for a federation region."""

    region_id: str
    active_jobs: int = 0
    queued_jobs: int = 0
    completed_jobs_24h: int = 0
    failed_jobs_24h: int = 0
    avg_latency_ms: float = 0.0
    avg_wait_time_s: float = 0.0
    cost_per_shot: float = 0.0
    last_updated: datetime = field(default_factory=lambda: datetime.now(UTC))


class RoutingPolicy(BaseModel):
    """Routing policy configuration."""

    name: str
    strategy: RoutingStrategy
    preferred_regions: list[str] = Field(default_factory=list)
    excluded_regions: list[str] = Field(default_factory=list)
    max_latency_ms: float | None = None
    max_cost_per_shot: float | None = None
    failover_enabled: bool = True
    retry_count: int = 3
    timeout_seconds: float = 300.0


class FederationConfig(BaseModel):
    """Federation configuration."""

    federation_id: str
    name: str
    routing_policy: RoutingPolicy
    regions: list[str]
    created_at: str
    updated_at: str


class RegionCreate(BaseModel):
    """Request to create a region."""

    name: str = Field(..., min_length=2, max_length=100)
    provider: ProviderType
    endpoint: str
    priority: int = Field(default=1, ge=1, le=100)
    weight: int = Field(default=100, ge=1, le=1000)
    max_concurrent_jobs: int = Field(default=10, ge=1)
    metadata: dict[str, Any] | None = None


class RegionResponse(BaseModel):
    """Region details response."""

    region_id: str
    name: str
    provider: ProviderType
    endpoint: str
    status: RegionStatus
    priority: int
    weight: int
    max_concurrent_jobs: int
    metrics: dict[str, Any] | None = None
    created_at: str
    last_health_check: str | None


class RoutingRequest(BaseModel):
    """Request to route a job."""

    job_type: str
    algorithm: str
    num_qubits: int
    shots: int = 1024
    preferred_region: str | None = None
    preferred_provider: ProviderType | None = None
    max_cost: float | None = None
    max_latency_ms: float | None = None
    require_real_hardware: bool = False


class RoutingDecision(BaseModel):
    """Routing decision response."""

    decision_id: str
    selected_region: str
    selected_provider: ProviderType
    endpoint: str
    estimated_cost: float
    estimated_latency_ms: float
    estimated_wait_time_s: float
    alternatives: list[dict[str, Any]]
    routing_reason: str


class FederationStatus(BaseModel):
    """Overall federation status."""

    federation_id: str
    total_regions: int
    healthy_regions: int
    degraded_regions: int
    offline_regions: int
    total_active_jobs: int
    routing_strategy: RoutingStrategy
    last_updated: str


_in_memory_regions: dict[str, FederationRegion] = {}
_region_metrics: dict[str, RegionMetrics] = {}
_routing_history: list[dict[str, Any]] = []


def seed_default_regions():
    """Seed default regions for common providers."""
    if _in_memory_regions:
        return

    default_regions = [
        {
            "name": "IBM-US-East",
            "provider": ProviderType.IBM,
            "endpoint": "https://auth.quantum.ibm.com/api",
            "priority": 1,
            "metadata": {"datacenter": "us-east", "qpus": ["ibm_brisbane", "ibm_kyiv"]},
        },
        {
            "name": "IBM-US-West",
            "provider": ProviderType.IBM,
            "endpoint": "https://auth.quantum.ibm.com/api",
            "priority": 2,
            "metadata": {"datacenter": "us-west", "qpus": ["ibm_seattle"]},
        },
        {
            "name": "AWS-US-East-1",
            "provider": ProviderType.AWS,
            "endpoint": "braket.us-east-1.amazonaws.com",
            "priority": 1,
            "metadata": {
                "region": "us-east-1",
                "devices": ["sv1", "ionq_aria", "rigetti_aspen_m3"],
            },
        },
        {
            "name": "AWS-US-West-1",
            "provider": ProviderType.AWS,
            "endpoint": "braket.us-west-1.amazonaws.com",
            "priority": 2,
            "metadata": {"region": "us-west-1", "devices": ["rigetti_aspen_m3"]},
        },
        {
            "name": "AWS-EU-North-1",
            "provider": ProviderType.AWS,
            "endpoint": "braket.eu-north-1.amazonaws.com",
            "priority": 3,
            "metadata": {"region": "eu-north-1", "devices": ["iqm_garnet"]},
        },
        {
            "name": "Azure-East-US",
            "provider": ProviderType.AZURE,
            "endpoint": "https://quantum.azure.com",
            "priority": 1,
            "metadata": {"region": "eastus", "providers": ["ionq", "quantinuum"]},
        },
        {
            "name": "Azure-West-EU",
            "provider": ProviderType.AZURE,
            "endpoint": "https://quantum.azure.com",
            "priority": 2,
            "metadata": {"region": "westeurope", "providers": ["ionq", "quantinuum"]},
        },
        {
            "name": "DWave-US-West",
            "provider": ProviderType.DWAVE,
            "endpoint": "https://cloud.dwavesys.com",
            "priority": 1,
            "metadata": {
                "solvers": ["Advantage_system6.4", "hybrid_binary_quadratic_model_version2"]
            },
        },
        {
            "name": "Local-Simulator",
            "provider": ProviderType.LOCAL,
            "endpoint": "localhost",
            "priority": 10,
            "metadata": {"type": "simulator", "devices": ["statevector", "tensor_network"]},
        },
    ]

    for region_data in default_regions:
        region = FederationRegion.create(
            name=region_data["name"],
            provider=region_data["provider"],
            endpoint=region_data["endpoint"],
            priority=region_data["priority"],
            **region_data.get("metadata", {}),
        )
        _in_memory_regions[region.region_id] = region
        _region_metrics[region.region_id] = RegionMetrics(
            region_id=region.region_id,
            active_jobs=0,
            avg_latency_ms=50.0 + hash(region.name) % 200,
            cost_per_shot=0.001 * (1 + region.priority * 0.5),
        )


def select_region(
    strategy: RoutingStrategy,
    preferred_region: str | None = None,
    preferred_provider: ProviderType | None = None,
    max_cost: float | None = None,
    max_latency_ms: float | None = None,
) -> tuple[FederationRegion, str]:
    """Select the best region based on routing strategy."""
    seed_default_regions()

    available = [
        r
        for r in _in_memory_regions.values()
        if r.status in (RegionStatus.HEALTHY, RegionStatus.DEGRADED)
    ]

    if preferred_region:
        for r in available:
            if r.region_id == preferred_region or r.name == preferred_region:
                return r, f"Preferred region selected: {r.name}"

    if preferred_provider:
        provider_regions = [r for r in available if r.provider == preferred_provider]
        if provider_regions:
            available = provider_regions

    if max_cost is not None:
        available = [
            r
            for r in available
            if _region_metrics.get(r.region_id, RegionMetrics(region_id=r.region_id)).cost_per_shot
            <= max_cost
        ]

    if max_latency_ms is not None:
        available = [
            r
            for r in available
            if _region_metrics.get(r.region_id, RegionMetrics(region_id=r.region_id)).avg_latency_ms
            <= max_latency_ms
        ]

    if not available:
        raise ValueError("No regions available matching criteria")

    if strategy == RoutingStrategy.LATENCY:
        available.sort(
            key=lambda r: (
                _region_metrics.get(
                    r.region_id, RegionMetrics(region_id=r.region_id)
                ).avg_latency_ms
            )
        )
        return available[0], "Selected for lowest latency"

    elif strategy == RoutingStrategy.COST:
        available.sort(
            key=lambda r: (
                _region_metrics.get(r.region_id, RegionMetrics(region_id=r.region_id)).cost_per_shot
            )
        )
        return available[0], "Selected for lowest cost"

    elif strategy == RoutingStrategy.LOAD_BALANCED:
        available.sort(
            key=lambda r: (
                _region_metrics.get(r.region_id, RegionMetrics(region_id=r.region_id)).active_jobs
            )
        )
        return available[0], "Selected for load balancing"

    elif strategy == RoutingStrategy.PRIORITY:
        available.sort(key=lambda r: r.priority)
        return available[0], "Selected by priority"

    elif strategy == RoutingStrategy.ROUND_ROBIN:
        import random

        return random.choice(available), "Round-robin selection"

    else:
        available.sort(
            key=lambda r: (
                r.priority,
                _region_metrics.get(r.region_id, RegionMetrics(region_id=r.region_id)).active_jobs,
            )
        )
        return available[0], "Default priority-based selection"


def get_federation_status() -> FederationStatus:
    """Get overall federation status."""
    seed_default_regions()

    regions = list(_in_memory_regions.values())
    healthy = sum(1 for r in regions if r.status == RegionStatus.HEALTHY)
    degraded = sum(1 for r in regions if r.status == RegionStatus.DEGRADED)
    offline = sum(1 for r in regions if r.status in (RegionStatus.OFFLINE, RegionStatus.UNHEALTHY))

    total_jobs = sum(m.active_jobs for m in _region_metrics.values())

    return FederationStatus(
        federation_id="fed_quantum_platform",
        total_regions=len(regions),
        healthy_regions=healthy,
        degraded_regions=degraded,
        offline_regions=offline,
        total_active_jobs=total_jobs,
        routing_strategy=RoutingStrategy.LOAD_BALANCED,
        last_updated=datetime.now(UTC).isoformat(),
    )
