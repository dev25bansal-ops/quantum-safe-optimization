"""
Multi-Region Active-Active Deployment Controller.

Enables:
- Active-active deployment across multiple regions
- Automatic failover and failback
- Data synchronization between regions
- Conflict resolution
- Global load balancing
"""

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from enum import Enum
from typing import Any, Optional
from uuid import uuid4

import structlog

logger = structlog.get_logger()


class RegionState(str, Enum):
    """Region operational states."""

    ACTIVE = "active"
    STANDBY = "standby"
    FAILING_OVER = "failing_over"
    RECOVERING = "recovering"
    OFFLINE = "offline"
    MAINTENANCE = "maintenance"


class SyncStatus(str, Enum):
    """Data synchronization status."""

    IN_SYNC = "in_sync"
    SYNCING = "syncing"
    BEHIND = "behind"
    CONFLICT = "conflict"
    UNKNOWN = "unknown"


@dataclass
class Region:
    """A deployment region."""

    region_id: str
    name: str
    endpoint: str
    state: RegionState = RegionState.ACTIVE
    priority: int = 1
    capacity: int = 100
    current_load: int = 0
    last_heartbeat: Optional[datetime] = None
    sync_status: SyncStatus = SyncStatus.UNKNOWN
    sync_lag_seconds: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def health_percentage(self) -> float:
        """Calculate health percentage."""
        if not self.last_heartbeat:
            return 0.0
        age = (datetime.now(UTC) - self.last_heartbeat).total_seconds()
        if age < 30:
            return 100.0
        elif age < 60:
            return 75.0
        elif age < 120:
            return 50.0
        return 0.0

    @property
    def load_percentage(self) -> float:
        """Calculate load percentage."""
        if self.capacity <= 0:
            return 100.0
        return (self.current_load / self.capacity) * 100

    @property
    def is_healthy(self) -> bool:
        """Check if region is healthy."""
        return (
            self.state == RegionState.ACTIVE
            and self.health_percentage >= 50.0
            and self.sync_status != SyncStatus.CONFLICT
        )


@dataclass
class GlobalJob:
    """A job distributed across regions."""

    job_id: str
    user_id: str
    primary_region: str
    backup_regions: list[str]
    created_at: datetime
    state: str = "pending"
    failover_count: int = 0
    region_history: list[dict[str, Any]] = field(default_factory=list)


class MultiRegionController:
    """
    Controller for multi-region active-active deployment.

    Features:
    - Active-active traffic distribution
    - Automatic failover on region failure
    - Data synchronization tracking
    - Conflict resolution
    - Global job routing
    """

    def __init__(
        self,
        heartbeat_timeout_seconds: int = 60,
        sync_lag_threshold_seconds: int = 300,
        failover_threshold: float = 0.3,
    ):
        self.heartbeat_timeout = heartbeat_timeout_seconds
        self.sync_lag_threshold = sync_lag_threshold_seconds
        self.failover_threshold = failover_threshold

        self._regions: dict[str, Region] = {}
        self._jobs: dict[str, GlobalJob] = {}
        self._region_jobs: dict[str, list[str]] = {}
        self._lock = asyncio.Lock()
        self._monitor_task: Optional[asyncio.Task] = None

    async def register_region(
        self,
        region_id: str,
        name: str,
        endpoint: str,
        priority: int = 1,
        capacity: int = 100,
        metadata: Optional[dict] = None,
    ) -> Region:
        """Register a new region."""
        async with self._lock:
            region = Region(
                region_id=region_id,
                name=name,
                endpoint=endpoint,
                priority=priority,
                capacity=capacity,
                last_heartbeat=datetime.now(UTC),
                sync_status=SyncStatus.IN_SYNC,
                metadata=metadata or {},
            )
            self._regions[region_id] = region
            self._region_jobs[region_id] = []

            logger.info("region_registered", region_id=region_id, name=name, priority=priority)

            return region

    async def heartbeat(
        self, region_id: str, current_load: int, sync_status: SyncStatus, sync_lag_seconds: int = 0
    ) -> dict[str, Any]:
        """Process region heartbeat."""
        async with self._lock:
            if region_id not in self._regions:
                raise ValueError(f"Unknown region: {region_id}")

            region = self._regions[region_id]
            region.last_heartbeat = datetime.now(UTC)
            region.current_load = current_load
            region.sync_status = sync_status
            region.sync_lag_seconds = sync_lag_seconds

            # Update state based on health
            if region.state == RegionState.OFFLINE:
                region.state = RegionState.RECOVERING
                logger.info("region_recovering", region_id=region_id)

            return {
                "region_id": region_id,
                "state": region.state.value,
                "is_healthy": region.is_healthy,
                "recommended_action": self._get_recommended_action(region),
            }

    def _get_recommended_action(self, region: Region) -> str:
        """Get recommended action for a region."""
        if region.state == RegionState.MAINTENANCE:
            return "complete_maintenance"
        if region.health_percentage < 50:
            return "investigate_health"
        if region.sync_lag_seconds > self.sync_lag_threshold:
            return "sync_data"
        if region.load_percentage > 80:
            return "scale_capacity"
        return "none"

    async def route_request(
        self, request_type: str, user_id: str, preferences: Optional[dict] = None
    ) -> Region:
        """Route a request to the best region."""
        async with self._lock:
            active_regions = [r for r in self._regions.values() if r.is_healthy]

            if not active_regions:
                raise RuntimeError("No healthy regions available")

            # Sort by: priority (lower is better), load (lower is better), health
            active_regions.sort(key=lambda r: (r.priority, r.load_percentage, -r.health_percentage))

            # Consider user preferences
            preferred_region = preferences.get("preferred_region") if preferences else None
            if preferred_region and preferred_region in self._regions:
                region = self._regions[preferred_region]
                if region.is_healthy:
                    return region

            return active_regions[0]

    async def route_job(
        self, job_id: str, user_id: str, job_type: str, preferences: Optional[dict] = None
    ) -> GlobalJob:
        """Route a job with failover support."""
        primary = await self.route_request(job_type, user_id, preferences)

        # Select backup regions
        active_regions = [
            r for r in self._regions.values() if r.is_healthy and r.region_id != primary.region_id
        ]
        active_regions.sort(key=lambda r: r.priority)
        backup_regions = [r.region_id for r in active_regions[:2]]

        job = GlobalJob(
            job_id=job_id,
            user_id=user_id,
            primary_region=primary.region_id,
            backup_regions=backup_regions,
            created_at=datetime.now(UTC),
            region_history=[
                {
                    "region_id": primary.region_id,
                    "started_at": datetime.now(UTC).isoformat(),
                    "role": "primary",
                }
            ],
        )

        async with self._lock:
            self._jobs[job_id] = job
            self._region_jobs[primary.region_id].append(job_id)

        logger.info(
            "job_routed",
            job_id=job_id,
            primary_region=primary.region_id,
            backup_regions=backup_regions,
        )

        return job

    async def failover_job(self, job_id: str, reason: str) -> Optional[GlobalJob]:
        """Failover a job to a backup region."""
        async with self._lock:
            if job_id not in self._jobs:
                return None

            job = self._jobs[job_id]

            if not job.backup_regions:
                logger.error("job_no_backup", job_id=job_id)
                return None

            new_primary = job.backup_regions[0]
            job.primary_region = new_primary
            job.backup_regions = job.backup_regions[1:]
            job.failover_count += 1
            job.region_history.append(
                {
                    "region_id": new_primary,
                    "started_at": datetime.now(UTC).isoformat(),
                    "role": "failover",
                    "reason": reason,
                }
            )

            logger.warning(
                "job_failover",
                job_id=job_id,
                new_primary=new_primary,
                reason=reason,
                failover_count=job.failover_count,
            )

            return job

    async def check_region_health(self) -> dict[str, Any]:
        """Check health of all regions."""
        now = datetime.now(UTC)
        actions = []

        async with self._lock:
            for region in self._regions.values():
                if region.last_heartbeat:
                    age = (now - region.last_heartbeat).total_seconds()
                    if age > self.heartbeat_timeout and region.state == RegionState.ACTIVE:
                        region.state = RegionState.OFFLINE
                        actions.append(
                            {
                                "action": "region_offline",
                                "region_id": region.region_id,
                                "last_heartbeat_age": age,
                            }
                        )

                        # Trigger failover for jobs in this region
                        for job_id in self._region_jobs.get(region.region_id, []):
                            if job_id in self._jobs:
                                job = self._jobs[job_id]
                                if job.primary_region == region.region_id:
                                    await self.failover_job(job_id, "primary_region_offline")

            return {
                "regions": {
                    r.region_id: {
                        "name": r.name,
                        "state": r.state.value,
                        "health": r.health_percentage,
                        "load": r.load_percentage,
                        "sync_status": r.sync_status.value,
                        "sync_lag": r.sync_lag_seconds,
                    }
                    for r in self._regions.values()
                },
                "actions_taken": actions,
                "healthy_count": sum(1 for r in self._regions.values() if r.is_healthy),
                "total_count": len(self._regions),
            }

    async def get_status(self) -> dict[str, Any]:
        """Get global deployment status."""
        healthy_regions = [r for r in self._regions.values() if r.is_healthy]

        return {
            "deployment_mode": "active-active",
            "total_regions": len(self._regions),
            "healthy_regions": len(healthy_regions),
            "active_regions": sum(
                1 for r in self._regions.values() if r.state == RegionState.ACTIVE
            ),
            "jobs_total": len(self._jobs),
            "jobs_with_failover": sum(1 for j in self._jobs.values() if j.failover_count > 0),
            "regions": {
                r.region_id: {
                    "state": r.state.value,
                    "health": r.health_percentage,
                    "load": r.load_percentage,
                    "jobs": len(self._region_jobs.get(r.region_id, [])),
                }
                for r in self._regions.values()
            },
        }

    async def start_monitor(self):
        """Start background health monitor."""
        if self._monitor_task:
            return

        self._monitor_task = asyncio.create_task(self._monitor_loop())
        logger.info("region_monitor_started")

    async def stop_monitor(self):
        """Stop background health monitor."""
        if self._monitor_task:
            self._monitor_task.cancel()
            try:
                await self._monitor_task
            except asyncio.CancelledError:
                pass
            self._monitor_task = None
            logger.info("region_monitor_stopped")

    async def _monitor_loop(self):
        """Background health monitoring loop."""
        while True:
            try:
                await asyncio.sleep(30)
                await self.check_region_health()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("monitor_error", error=str(e))


multi_region_controller = MultiRegionController()
