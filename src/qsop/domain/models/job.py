"""
Job-related domain models.

Defines structures for job specifications, status tracking, and results
with encrypted artifact references.
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any
from uuid import UUID, uuid4

from qsop.domain.models.problem import OptimizationProblem


class JobStatus(Enum):
    """Status of an optimization job."""

    PENDING = "pending"
    QUEUED = "queued"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"

    def is_terminal(self) -> bool:
        """Check if this status represents a terminal state."""
        return self in (JobStatus.COMPLETED, JobStatus.FAILED, JobStatus.CANCELLED)

    def is_active(self) -> bool:
        """Check if this status represents an active job."""
        return self in (JobStatus.QUEUED, JobStatus.RUNNING, JobStatus.PAUSED)


@dataclass(frozen=True)
class CryptoSettings:
    """
    Cryptographic settings for a job.

    Attributes:
        kem_algorithm: Key encapsulation mechanism algorithm name.
        signature_algorithm: Digital signature algorithm name.
        key_id: ID of the key to use for encryption.
        encrypt_artifacts: Whether to encrypt job artifacts.
        sign_results: Whether to sign job results.
    """

    kem_algorithm: str = "ML-KEM-768"
    signature_algorithm: str = "ML-DSA-65"
    key_id: str | None = None
    encrypt_artifacts: bool = True
    sign_results: bool = True


@dataclass(frozen=True)
class BackendSettings:
    """
    Quantum backend configuration for a job.

    Attributes:
        backend_name: Name of the quantum backend.
        shots: Number of measurement shots.
        optimization_level: Transpiler optimization level (0-3).
        resilience_level: Error mitigation level.
        max_execution_time: Maximum execution time in seconds.
        custom_options: Backend-specific custom options.
    """

    backend_name: str
    shots: int = 1024
    optimization_level: int = 1
    resilience_level: int = 1
    max_execution_time: int | None = None
    custom_options: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class AlgorithmSettings:
    """
    Algorithm configuration for optimization.

    Attributes:
        algorithm_name: Name of the optimization algorithm.
        max_iterations: Maximum number of iterations.
        convergence_threshold: Threshold for convergence detection.
        warm_start: Whether to use warm starting.
        algorithm_params: Algorithm-specific parameters.
    """

    algorithm_name: str
    max_iterations: int = 100
    convergence_threshold: float = 1e-6
    warm_start: bool = False
    algorithm_params: dict[str, Any] = field(default_factory=dict)


@dataclass
class JobSpec:
    """
    Complete specification for an optimization job.

    Attributes:
        id: Unique job identifier.
        problem: The optimization problem to solve.
        algorithm: Algorithm configuration.
        backend: Quantum backend configuration (if using quantum).
        crypto: Cryptographic settings.
        priority: Job priority (higher = more priority).
        tags: Tags for job categorization.
        metadata: Additional job metadata.
        created_at: Job creation timestamp.
        owner_id: ID of the job owner.
    """

    problem: OptimizationProblem
    algorithm: AlgorithmSettings
    backend: BackendSettings | None = None
    crypto: CryptoSettings = field(default_factory=CryptoSettings)
    id: UUID = field(default_factory=uuid4)
    priority: int = 0
    tags: tuple[str, ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.utcnow)
    owner_id: str | None = None

    @property
    def is_quantum_job(self) -> bool:
        """Check if this job requires quantum execution."""
        return self.backend is not None

    @property
    def is_encrypted(self) -> bool:
        """Check if artifacts should be encrypted."""
        return self.crypto.encrypt_artifacts


@dataclass
class JobResult:
    """
    Result of a completed optimization job.

    Attributes:
        job_id: ID of the job this result belongs to.
        status: Final job status.
        result_artifact_id: ID of the encrypted result artifact.
        circuit_artifact_ids: IDs of circuit artifacts (for quantum jobs).
        parameter_snapshot_ids: IDs of parameter snapshot artifacts.
        signature: Digital signature of the result (if signing enabled).
        error_message: Error message if job failed.
        started_at: When job execution started.
        completed_at: When job execution completed.
        execution_time_seconds: Total execution time.
        metadata: Additional result metadata.
    """

    job_id: UUID
    status: JobStatus
    result_artifact_id: UUID | None = None
    circuit_artifact_ids: tuple[UUID, ...] = ()
    parameter_snapshot_ids: tuple[UUID, ...] = ()
    signature: bytes | None = None
    error_message: str | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None
    execution_time_seconds: float | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def is_successful(self) -> bool:
        """Check if the job completed successfully."""
        return self.status == JobStatus.COMPLETED and self.result_artifact_id is not None

    @property
    def has_signature(self) -> bool:
        """Check if the result has a digital signature."""
        return self.signature is not None
