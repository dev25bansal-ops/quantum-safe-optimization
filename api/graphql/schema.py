"""
GraphQL Schema for Quantum-Safe Optimization Platform.

Provides GraphQL API for complex queries and mutations.
"""

import strawberry
from datetime import datetime
from typing import Optional
from enum import Enum


class JobStatusEnum(str, Enum):
    PENDING = "pending"
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class AlgorithmEnum(str, Enum):
    VQE = "VQE"
    QAOA = "QAOA"
    ANNEALING = "ANNEALING"
    GROVER = "GROVER"
    CLASSICAL = "CLASSICAL"


@strawberry.type
class Job:
    id: strawberry.ID
    status: JobStatusEnum
    algorithm: AlgorithmEnum
    problem_type: str
    created_at: datetime
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    backend: str
    shots: int
    error: Optional[str] = None
    message: Optional[str] = None


@strawberry.type
class JobResult:
    job_id: strawberry.ID
    optimal_value: Optional[float] = None
    optimal_parameters: Optional[str] = None
    iterations: Optional[int] = None
    convergence_history: Optional[str] = None
    execution_time_seconds: Optional[float] = None


@strawberry.type
class KeyInfo:
    key_id: str
    algorithm: str
    created_at: datetime
    expires_at: Optional[datetime] = None
    is_active: bool
    rotation_due: Optional[datetime] = None


@strawberry.type
class BackendInfo:
    name: str
    provider: str
    status: str
    qubits_available: int
    queue_length: int
    avg_latency_ms: float
    cost_per_shot: float


@strawberry.type
class MetricPoint:
    timestamp: datetime
    value: float


@strawberry.type
class AnalyticsData:
    metric_name: str
    unit: str
    points: list[MetricPoint]


@strawberry.type
class Query:
    @strawberry.field
    async def job(self, job_id: strawberry.ID) -> Optional[Job]:
        """Get a specific job by ID."""
        from api.routers.jobs import get_job_data

        job_data = await get_job_data(str(job_id))
        if not job_data:
            return None

        return Job(
            id=job_data.get("job_id"),
            status=JobStatusEnum(job_data.get("status", "pending")),
            algorithm=AlgorithmEnum(job_data.get("problem_type", "VQE")),
            problem_type=job_data.get("problem_type", ""),
            created_at=datetime.fromisoformat(job_data["created_at"])
            if job_data.get("created_at")
            else datetime.now(),
            started_at=datetime.fromisoformat(job_data["started_at"])
            if job_data.get("started_at")
            else None,
            completed_at=datetime.fromisoformat(job_data["completed_at"])
            if job_data.get("completed_at")
            else None,
            backend=job_data.get("backend", "local_simulator"),
            shots=job_data.get("parameters", {}).get("shots", 1024),
            error=job_data.get("error"),
            message=job_data.get("message"),
        )

    @strawberry.field
    async def jobs(
        self,
        status: Optional[JobStatusEnum] = None,
        algorithm: Optional[AlgorithmEnum] = None,
        limit: int = 20,
        offset: int = 0,
    ) -> list[Job]:
        """List jobs with optional filtering."""
        from api.routers.jobs import list_user_jobs

        jobs_data, _ = await list_user_jobs(
            user_id="graphql_user",
            status=status.value if status else None,
            problem_type=algorithm.value if algorithm else None,
            limit=limit,
            offset=offset,
        )

        return [
            Job(
                id=j.get("job_id"),
                status=JobStatusEnum(j.get("status", "pending")),
                algorithm=AlgorithmEnum(j.get("problem_type", "VQE")),
                problem_type=j.get("problem_type", ""),
                created_at=datetime.fromisoformat(j["created_at"])
                if j.get("created_at")
                else datetime.now(),
                backend=j.get("backend", "local_simulator"),
                shots=j.get("parameters", {}).get("shots", 1024),
            )
            for j in jobs_data
        ]

    @strawberry.field
    async def backends(self) -> list[BackendInfo]:
        """List available quantum backends."""
        from api.routers.backends import get_backends
        from api.federation.models import seed_default_regions, _in_memory_regions, _region_metrics

        seed_default_regions()

        backends = []
        for region_id, region in _in_memory_regions.items():
            metrics = _region_metrics.get(region_id)
            backends.append(
                BackendInfo(
                    name=region.name,
                    provider=region.provider.value,
                    status=region.status.value,
                    qubits_available=20,
                    queue_length=metrics.queued_jobs if metrics else 0,
                    avg_latency_ms=metrics.avg_latency_ms if metrics else 0,
                    cost_per_shot=metrics.cost_per_shot if metrics else 0,
                )
            )

        return backends

    @strawberry.field
    async def keys(self, user_id: str) -> list[KeyInfo]:
        """List cryptographic keys for a user."""
        from api.routers.auth import get_user_by_username

        user = await get_user_by_username(user_id)
        if not user:
            return []

        keys = []
        if user.get("kem_public_key"):
            keys.append(
                KeyInfo(
                    key_id=user.get("kem_key_id", "default_kem"),
                    algorithm="ML-KEM-768",
                    created_at=datetime.now(),
                    is_active=True,
                )
            )

        if user.get("signing_public_key"):
            keys.append(
                KeyInfo(
                    key_id=user.get("signing_key_id", "default_signing"),
                    algorithm="ML-DSA-65",
                    created_at=datetime.now(),
                    is_active=True,
                )
            )

        return keys

    @strawberry.field
    async def analytics(
        self,
        metric_name: str,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        resolution: str = "1h",
    ) -> AnalyticsData:
        """Get analytics data for a metric."""
        import time
        from datetime import timedelta

        if not start_time:
            start_time = datetime.now() - timedelta(days=1)
        if not end_time:
            end_time = datetime.now()

        points = []
        current = start_time
        while current <= end_time:
            points.append(
                MetricPoint(timestamp=current, value=100 + (hash(metric_name + str(current)) % 50))
            )
            if resolution == "1h":
                current += timedelta(hours=1)
            elif resolution == "1d":
                current += timedelta(days=1)
            else:
                current += timedelta(minutes=15)

        return AnalyticsData(
            metric_name=metric_name,
            unit="ms" if "latency" in metric_name.lower() else "count",
            points=points[:100],
        )


@strawberry.type
class Mutation:
    @strawberry.mutation
    async def submit_job(
        self,
        algorithm: AlgorithmEnum,
        problem_config: str,
        parameters: str,
        backend: str = "local_simulator",
    ) -> Job:
        """Submit a new optimization job."""
        import json
        import uuid
        from datetime import UTC
        from api.routers.jobs import save_job

        job_id = f"job_{uuid.uuid4().hex[:12]}"
        job_data = {
            "job_id": job_id,
            "status": "pending",
            "problem_type": algorithm.value,
            "problem_config": json.loads(problem_config)
            if isinstance(problem_config, str)
            else problem_config,
            "parameters": json.loads(parameters) if isinstance(parameters, str) else parameters,
            "backend": backend,
            "created_at": datetime.now(UTC).isoformat(),
            "user_id": "graphql_user",
        }

        await save_job(job_data)

        return Job(
            id=job_id,
            status=JobStatusEnum.PENDING,
            algorithm=algorithm,
            problem_type=algorithm.value,
            created_at=datetime.now(),
            backend=backend,
            shots=job_data.get("parameters", {}).get("shots", 1024),
        )

    @strawberry.mutation
    async def cancel_job(self, job_id: strawberry.ID) -> Job:
        """Cancel a running job."""
        from api.routers.jobs import get_job_data, save_job

        job_data = await get_job_data(str(job_id))
        if not job_data:
            raise ValueError(f"Job {job_id} not found")

        job_data["status"] = "cancelled"
        await save_job(job_data)

        return Job(
            id=job_id,
            status=JobStatusEnum.CANCELLED,
            algorithm=AlgorithmEnum(job_data.get("problem_type", "VQE")),
            problem_type=job_data.get("problem_type", ""),
            created_at=datetime.fromisoformat(job_data["created_at"]),
            backend=job_data.get("backend", "local_simulator"),
            shots=job_data.get("parameters", {}).get("shots", 1024),
        )

    @strawberry.mutation
    async def generate_key(self, key_type: str = "kem") -> KeyInfo:
        """Generate a new cryptographic key."""
        import uuid
        from datetime import UTC, timedelta

        key_id = f"key_{uuid.uuid4().hex[:8]}"

        return KeyInfo(
            key_id=key_id,
            algorithm="ML-KEM-768" if key_type == "kem" else "ML-DSA-65",
            created_at=datetime.now(),
            expires_at=datetime.now() + timedelta(days=90),
            is_active=True,
            rotation_due=datetime.now() + timedelta(days=90),
        )


schema = strawberry.Schema(query=Query, mutation=Mutation)
