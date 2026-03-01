"""
QuantumSafe Client - Data models.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any


class JobStatus(str, Enum):
    """Job execution status."""

    PENDING = "pending"
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class JobType(str, Enum):
    """Type of quantum optimization job."""

    QAOA = "qaoa"
    VQE = "vqe"
    ANNEALING = "annealing"


@dataclass
class Job:
    """
    Represents a quantum optimization job.

    Attributes:
        id: Unique job identifier
        job_type: Type of optimization (QAOA, VQE, Annealing)
        status: Current execution status
        backend: Quantum backend used
        created_at: Job creation timestamp
        updated_at: Last update timestamp
        started_at: Execution start time
        completed_at: Execution completion time
        config: Job configuration parameters
        result: Job execution results (when completed)
        error: Error message (when failed)
        progress: Execution progress (0-100)
        webhook_url: URL for completion notification
    """

    id: str
    job_type: JobType
    status: JobStatus
    backend: str
    created_at: datetime
    updated_at: datetime | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None
    config: dict[str, Any] = field(default_factory=dict)
    result: dict[str, Any] | None = None
    error: str | None = None
    progress: float = 0.0
    webhook_url: str | None = None

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Job:
        """Create Job from API response dictionary."""
        # Parse timestamps
        created_at = data.get("created_at")
        if isinstance(created_at, str):
            created_at = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
        elif created_at is None:
            created_at = datetime.now()

        updated_at = data.get("updated_at")
        if isinstance(updated_at, str):
            updated_at = datetime.fromisoformat(updated_at.replace("Z", "+00:00"))

        started_at = data.get("started_at")
        if isinstance(started_at, str):
            started_at = datetime.fromisoformat(started_at.replace("Z", "+00:00"))

        completed_at = data.get("completed_at")
        if isinstance(completed_at, str):
            completed_at = datetime.fromisoformat(completed_at.replace("Z", "+00:00"))

        # Parse enums
        job_type = data.get("job_type", "qaoa")
        if isinstance(job_type, str):
            job_type = JobType(job_type.lower())

        status = data.get("status", "pending")
        if isinstance(status, str):
            status = JobStatus(status.lower())

        return cls(
            id=data.get("id", data.get("job_id", "")),
            job_type=job_type,
            status=status,
            backend=data.get("backend", "simulator"),
            created_at=created_at,
            updated_at=updated_at,
            started_at=started_at,
            completed_at=completed_at,
            config=data.get("config", {}),
            result=data.get("result"),
            error=data.get("error"),
            progress=data.get("progress", 0.0),
            webhook_url=data.get("webhook_url"),
        )

    def to_dict(self) -> dict[str, Any]:
        """Convert Job to dictionary."""
        return {
            "id": self.id,
            "job_type": self.job_type.value,
            "status": self.status.value,
            "backend": self.backend,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "config": self.config,
            "result": self.result,
            "error": self.error,
            "progress": self.progress,
            "webhook_url": self.webhook_url,
        }

    @property
    def is_complete(self) -> bool:
        """Check if job has finished (completed, failed, or cancelled)."""
        return self.status in [JobStatus.COMPLETED, JobStatus.FAILED, JobStatus.CANCELLED]

    @property
    def is_successful(self) -> bool:
        """Check if job completed successfully."""
        return self.status == JobStatus.COMPLETED

    @property
    def duration(self) -> float | None:
        """Get job duration in seconds, if completed."""
        if self.started_at and self.completed_at:
            return (self.completed_at - self.started_at).total_seconds()
        return None


@dataclass
class QAOAConfig:
    """
    Configuration for QAOA optimization jobs.

    Attributes:
        p: Number of QAOA layers (circuit depth parameter)
        shots: Number of measurement shots
        optimizer: Classical optimizer (COBYLA, SPSA, etc.)
        initial_params: Initial variational parameters
        max_iterations: Maximum optimizer iterations
    """

    p: int = 1
    shots: int = 1000
    optimizer: str = "COBYLA"
    initial_params: list[float] | None = None
    max_iterations: int = 100

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "p": self.p,
            "shots": self.shots,
            "optimizer": self.optimizer,
            "initial_params": self.initial_params,
            "max_iterations": self.max_iterations,
        }


@dataclass
class VQEConfig:
    """
    Configuration for VQE optimization jobs.

    Attributes:
        ansatz: Variational ansatz type (uccsd, hardware_efficient, etc.)
        shots: Number of measurement shots
        optimizer: Classical optimizer
        initial_params: Initial variational parameters
        max_iterations: Maximum optimizer iterations
    """

    ansatz: str = "uccsd"
    shots: int = 1000
    optimizer: str = "COBYLA"
    initial_params: list[float] | None = None
    max_iterations: int = 100

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "ansatz": self.ansatz,
            "shots": self.shots,
            "optimizer": self.optimizer,
            "initial_params": self.initial_params,
            "max_iterations": self.max_iterations,
        }


@dataclass
class AnnealingConfig:
    """
    Configuration for quantum annealing jobs.

    Attributes:
        num_reads: Number of annealing reads/samples
        annealing_time: Annealing time in microseconds
        chain_strength: Chain strength for embedding
        auto_scale: Whether to auto-scale problem
    """

    num_reads: int = 1000
    annealing_time: int = 20
    chain_strength: float | None = None
    auto_scale: bool = True

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "num_reads": self.num_reads,
            "annealing_time": self.annealing_time,
            "chain_strength": self.chain_strength,
            "auto_scale": self.auto_scale,
        }


@dataclass
class CostEstimate:
    """
    Cost estimate for a quantum job.

    Attributes:
        backend: Target quantum backend
        job_type: Type of optimization job
        estimated_cost_usd: Estimated cost in USD
        estimated_time_seconds: Estimated execution time
        shots: Number of shots/reads
        currency: Currency code
        breakdown: Detailed cost breakdown
        notes: Additional notes about pricing
    """

    backend: str
    job_type: str
    estimated_cost_usd: float
    estimated_time_seconds: float
    shots: int
    currency: str = "USD"
    breakdown: dict[str, float] | None = None
    notes: str | None = None

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> CostEstimate:
        """Create CostEstimate from API response dictionary."""
        return cls(
            backend=data.get("backend", "unknown"),
            job_type=data.get("job_type", "unknown"),
            estimated_cost_usd=data.get("estimated_cost_usd", 0.0),
            estimated_time_seconds=data.get("estimated_time_seconds", 0.0),
            shots=data.get("shots", 0),
            currency=data.get("currency", "USD"),
            breakdown=data.get("breakdown"),
            notes=data.get("notes"),
        )

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "backend": self.backend,
            "job_type": self.job_type,
            "estimated_cost_usd": self.estimated_cost_usd,
            "estimated_time_seconds": self.estimated_time_seconds,
            "shots": self.shots,
            "currency": self.currency,
            "breakdown": self.breakdown,
            "notes": self.notes,
        }


@dataclass
class QuantumBackend:
    """
    Represents a quantum computing backend.

    Attributes:
        name: Backend identifier
        provider: Backend provider (IBM, AWS, D-Wave, etc.)
        backend_type: Type (gate-based, annealing)
        num_qubits: Number of qubits available
        status: Current operational status
        queue_length: Current queue length
        pricing: Pricing information
        features: Supported features
    """

    name: str
    provider: str
    backend_type: str
    num_qubits: int
    status: str = "online"
    queue_length: int = 0
    pricing: dict[str, Any] | None = None
    features: list[str] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> QuantumBackend:
        """Create QuantumBackend from API response dictionary."""
        return cls(
            name=data.get("name", "unknown"),
            provider=data.get("provider", "unknown"),
            backend_type=data.get("backend_type", data.get("type", "gate-based")),
            num_qubits=data.get("num_qubits", data.get("qubits", 0)),
            status=data.get("status", "unknown"),
            queue_length=data.get("queue_length", 0),
            pricing=data.get("pricing"),
            features=data.get("features", []),
        )

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "name": self.name,
            "provider": self.provider,
            "backend_type": self.backend_type,
            "num_qubits": self.num_qubits,
            "status": self.status,
            "queue_length": self.queue_length,
            "pricing": self.pricing,
            "features": self.features,
        }

    @property
    def is_available(self) -> bool:
        """Check if backend is available for jobs."""
        return self.status.lower() in ["online", "available", "operational"]
