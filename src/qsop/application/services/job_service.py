"""
Job Service for QSOP.

Provides job lifecycle management including submission, retrieval,
cancellation, and listing of optimization jobs.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional, Protocol
from uuid import UUID, uuid4

logger = logging.getLogger(__name__)


class JobStatus(str, Enum):
    """Job execution status."""
    
    PENDING = "pending"
    VALIDATING = "validating"
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class JobPriority(str, Enum):
    """Job priority levels."""
    
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class JobSpec:
    """Specification for an optimization job."""
    
    problem_type: str
    algorithm: str
    parameters: Dict[str, Any]
    backend: str = "simulator"
    max_iterations: int = 100
    convergence_threshold: float = 1e-6
    timeout_seconds: Optional[int] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class JobResult:
    """Result of an optimization job."""
    
    optimal_value: float
    optimal_params: Dict[str, Any]
    iterations: int
    convergence_history: List[float]
    execution_time_seconds: float
    backend_info: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class Job:
    """Represents an optimization job."""
    
    id: UUID
    tenant_id: str
    spec: JobSpec
    status: JobStatus
    priority: JobPriority
    created_at: datetime
    updated_at: datetime
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    result: Optional[JobResult] = None
    error_message: Optional[str] = None
    progress: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)


class JobRepository(Protocol):
    """Protocol for job persistence."""
    
    async def save(self, job: Job) -> None:
        """Save a job."""
        ...
    
    async def get(self, job_id: UUID) -> Optional[Job]:
        """Get a job by ID."""
        ...
    
    async def list_by_tenant(
        self,
        tenant_id: str,
        status: Optional[JobStatus] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[Job]:
        """List jobs for a tenant."""
        ...
    
    async def update(self, job: Job) -> None:
        """Update a job."""
        ...
    
    async def delete(self, job_id: UUID) -> bool:
        """Delete a job."""
        ...


class JobValidator(Protocol):
    """Protocol for job validation."""
    
    async def validate(self, spec: JobSpec, tenant_id: str) -> List[str]:
        """Validate a job spec. Returns list of validation errors."""
        ...


class JobPreprocessor(Protocol):
    """Protocol for job preprocessing."""
    
    async def preprocess(self, spec: JobSpec) -> JobSpec:
        """Preprocess a job spec before execution."""
        ...


class ResultAggregator(Protocol):
    """Protocol for result aggregation."""
    
    async def aggregate(self, results: List[JobResult]) -> JobResult:
        """Aggregate multiple job results."""
        ...


class InMemoryJobRepository:
    """In-memory implementation of job repository."""
    
    def __init__(self) -> None:
        self._jobs: Dict[UUID, Job] = {}
        self._lock = asyncio.Lock()
    
    async def save(self, job: Job) -> None:
        async with self._lock:
            self._jobs[job.id] = job
    
    async def get(self, job_id: UUID) -> Optional[Job]:
        return self._jobs.get(job_id)
    
    async def list_by_tenant(
        self,
        tenant_id: str,
        status: Optional[JobStatus] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[Job]:
        jobs = [
            j for j in self._jobs.values()
            if j.tenant_id == tenant_id
            and (status is None or j.status == status)
        ]
        jobs.sort(key=lambda j: j.created_at, reverse=True)
        return jobs[offset:offset + limit]
    
    async def update(self, job: Job) -> None:
        async with self._lock:
            job.updated_at = datetime.now(timezone.utc)
            self._jobs[job.id] = job
    
    async def delete(self, job_id: UUID) -> bool:
        async with self._lock:
            if job_id in self._jobs:
                del self._jobs[job_id]
                return True
            return False


class DefaultJobValidator:
    """Default job validator implementation."""
    
    SUPPORTED_ALGORITHMS = {"vqe", "qaoa", "grover", "spsa", "cobyla", "nelder-mead"}
    SUPPORTED_BACKENDS = {"simulator", "ibm_qasm", "ionq", "rigetti"}
    
    async def validate(self, spec: JobSpec, tenant_id: str) -> List[str]:
        errors: List[str] = []
        
        if not spec.problem_type:
            errors.append("problem_type is required")
        
        if spec.algorithm.lower() not in self.SUPPORTED_ALGORITHMS:
            errors.append(f"Unsupported algorithm: {spec.algorithm}")
        
        if spec.backend.lower() not in self.SUPPORTED_BACKENDS:
            errors.append(f"Unsupported backend: {spec.backend}")
        
        if spec.max_iterations < 1:
            errors.append("max_iterations must be positive")
        
        if spec.convergence_threshold <= 0:
            errors.append("convergence_threshold must be positive")
        
        if spec.timeout_seconds is not None and spec.timeout_seconds < 1:
            errors.append("timeout_seconds must be positive")
        
        return errors


class DefaultJobPreprocessor:
    """Default job preprocessor implementation."""
    
    async def preprocess(self, spec: JobSpec) -> JobSpec:
        # Normalize algorithm name
        normalized_params = dict(spec.parameters)
        
        # Add default parameters if not present
        if "seed" not in normalized_params:
            normalized_params["seed"] = 42
        
        return JobSpec(
            problem_type=spec.problem_type.lower(),
            algorithm=spec.algorithm.lower(),
            parameters=normalized_params,
            backend=spec.backend.lower(),
            max_iterations=spec.max_iterations,
            convergence_threshold=spec.convergence_threshold,
            timeout_seconds=spec.timeout_seconds,
            metadata=spec.metadata,
        )


class DefaultResultAggregator:
    """Default result aggregator implementation."""
    
    async def aggregate(self, results: List[JobResult]) -> JobResult:
        if not results:
            raise ValueError("No results to aggregate")
        
        if len(results) == 1:
            return results[0]
        
        # Find best result
        best = min(results, key=lambda r: r.optimal_value)
        
        # Aggregate metadata
        total_time = sum(r.execution_time_seconds for r in results)
        total_iterations = sum(r.iterations for r in results)
        
        return JobResult(
            optimal_value=best.optimal_value,
            optimal_params=best.optimal_params,
            iterations=total_iterations,
            convergence_history=best.convergence_history,
            execution_time_seconds=total_time,
            backend_info=best.backend_info,
            metadata={
                "aggregated_from": len(results),
                "all_optimal_values": [r.optimal_value for r in results],
            },
        )


class JobService:
    """
    Service for managing optimization job lifecycle.
    
    Provides operations for submitting, retrieving, cancelling,
    and listing jobs with proper validation and preprocessing.
    """
    
    def __init__(
        self,
        repository: Optional[JobRepository] = None,
        validator: Optional[JobValidator] = None,
        preprocessor: Optional[JobPreprocessor] = None,
        aggregator: Optional[ResultAggregator] = None,
    ) -> None:
        self._repository = repository or InMemoryJobRepository()
        self._validator = validator or DefaultJobValidator()
        self._preprocessor = preprocessor or DefaultJobPreprocessor()
        self._aggregator = aggregator or DefaultResultAggregator()
        self._running_jobs: Dict[UUID, asyncio.Task[None]] = {}
    
    async def submit_job(
        self,
        spec: JobSpec,
        tenant_id: str,
        priority: JobPriority = JobPriority.NORMAL,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Job:
        """
        Submit a new optimization job.
        
        Args:
            spec: Job specification
            tenant_id: Tenant identifier
            priority: Job priority
            metadata: Additional metadata
            
        Returns:
            Created job
            
        Raises:
            ValueError: If job validation fails
        """
        logger.info(f"Submitting job for tenant {tenant_id}, algorithm: {spec.algorithm}")
        
        # Validate job spec
        errors = await self._validator.validate(spec, tenant_id)
        if errors:
            error_msg = "; ".join(errors)
            logger.warning(f"Job validation failed: {error_msg}")
            raise ValueError(f"Job validation failed: {error_msg}")
        
        # Preprocess job spec
        processed_spec = await self._preprocessor.preprocess(spec)
        
        now = datetime.now(timezone.utc)
        job = Job(
            id=uuid4(),
            tenant_id=tenant_id,
            spec=processed_spec,
            status=JobStatus.PENDING,
            priority=priority,
            created_at=now,
            updated_at=now,
            metadata=metadata or {},
        )
        
        await self._repository.save(job)
        logger.info(f"Job {job.id} submitted successfully")
        
        return job
    
    async def get_job(self, job_id: UUID, tenant_id: str) -> Optional[Job]:
        """
        Get a job by ID.
        
        Args:
            job_id: Job identifier
            tenant_id: Tenant identifier (for authorization)
            
        Returns:
            Job if found and authorized, None otherwise
        """
        job = await self._repository.get(job_id)
        
        if job is None:
            logger.debug(f"Job {job_id} not found")
            return None
        
        if job.tenant_id != tenant_id:
            logger.warning(f"Unauthorized access attempt to job {job_id} by tenant {tenant_id}")
            return None
        
        return job
    
    async def cancel_job(self, job_id: UUID, tenant_id: str) -> bool:
        """
        Cancel a running or pending job.
        
        Args:
            job_id: Job identifier
            tenant_id: Tenant identifier (for authorization)
            
        Returns:
            True if cancelled, False otherwise
        """
        job = await self.get_job(job_id, tenant_id)
        
        if job is None:
            return False
        
        if job.status in (JobStatus.COMPLETED, JobStatus.FAILED, JobStatus.CANCELLED):
            logger.debug(f"Job {job_id} already in terminal state: {job.status}")
            return False
        
        # Cancel running task if exists
        if job_id in self._running_jobs:
            task = self._running_jobs[job_id]
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
            del self._running_jobs[job_id]
        
        job.status = JobStatus.CANCELLED
        job.completed_at = datetime.now(timezone.utc)
        await self._repository.update(job)
        
        logger.info(f"Job {job_id} cancelled")
        return True
    
    async def list_jobs(
        self,
        tenant_id: str,
        status: Optional[JobStatus] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[Job]:
        """
        List jobs for a tenant.
        
        Args:
            tenant_id: Tenant identifier
            status: Filter by status
            limit: Maximum number of jobs to return
            offset: Offset for pagination
            
        Returns:
            List of jobs
        """
        jobs = await self._repository.list_by_tenant(
            tenant_id=tenant_id,
            status=status,
            limit=limit,
            offset=offset,
        )
        logger.debug(f"Listed {len(jobs)} jobs for tenant {tenant_id}")
        return jobs
    
    async def update_job_status(
        self,
        job_id: UUID,
        status: JobStatus,
        progress: Optional[float] = None,
        error_message: Optional[str] = None,
    ) -> Optional[Job]:
        """
        Update job status (internal use).
        
        Args:
            job_id: Job identifier
            status: New status
            progress: Progress percentage (0-100)
            error_message: Error message if failed
            
        Returns:
            Updated job or None if not found
        """
        job = await self._repository.get(job_id)
        
        if job is None:
            return None
        
        job.status = status
        
        if progress is not None:
            job.progress = progress
        
        if error_message is not None:
            job.error_message = error_message
        
        if status == JobStatus.RUNNING and job.started_at is None:
            job.started_at = datetime.now(timezone.utc)
        
        if status in (JobStatus.COMPLETED, JobStatus.FAILED, JobStatus.CANCELLED):
            job.completed_at = datetime.now(timezone.utc)
        
        await self._repository.update(job)
        return job
    
    async def set_job_result(self, job_id: UUID, result: JobResult) -> Optional[Job]:
        """
        Set the result of a completed job.
        
        Args:
            job_id: Job identifier
            result: Job result
            
        Returns:
            Updated job or None if not found
        """
        job = await self._repository.get(job_id)
        
        if job is None:
            return None
        
        job.result = result
        job.status = JobStatus.COMPLETED
        job.progress = 100.0
        job.completed_at = datetime.now(timezone.utc)
        
        await self._repository.update(job)
        logger.info(f"Job {job_id} completed with optimal value: {result.optimal_value}")
        
        return job
    
    async def aggregate_results(self, job_ids: List[UUID], tenant_id: str) -> JobResult:
        """
        Aggregate results from multiple jobs.
        
        Args:
            job_ids: List of job identifiers
            tenant_id: Tenant identifier
            
        Returns:
            Aggregated result
            
        Raises:
            ValueError: If no valid results found
        """
        results: List[JobResult] = []
        
        for job_id in job_ids:
            job = await self.get_job(job_id, tenant_id)
            if job is not None and job.result is not None:
                results.append(job.result)
        
        if not results:
            raise ValueError("No valid results found for aggregation")
        
        return await self._aggregator.aggregate(results)
