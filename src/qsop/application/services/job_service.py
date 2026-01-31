"""
Job Service for QSOP.

Provides job lifecycle management including submission, retrieval,
cancellation, and listing of optimization jobs.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Protocol
from uuid import UUID, uuid4

from qsop.domain.models.job import JobSpec, JobResult, JobStatus, AlgorithmSettings, BackendSettings
from qsop.domain.models.problem import OptimizationProblem
from qsop.domain.ports.job_store import JobStore
from qsop.domain.ports.event_bus import EventBus, DomainEvent, EventTypes

logger = logging.getLogger(__name__)


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


class DefaultJobValidator:
    """Default job validator implementation."""
    
    SUPPORTED_ALGORITHMS = {"vqe", "qaoa", "grover", "spsa", "cobyla", "nelder-mead"}
    SUPPORTED_BACKENDS = {"simulator", "ibm_qasm", "ionq", "rigetti"}
    
    async def validate(self, spec: JobSpec, tenant_id: str) -> List[str]:
        errors: List[str] = []
        
        alg_name = spec.algorithm.algorithm_name.lower()
        if alg_name not in self.SUPPORTED_ALGORITHMS:
            errors.append(f"Unsupported algorithm: {alg_name}")
        
        if spec.backend:
            backend_name = spec.backend.backend_name.lower()
            if backend_name not in self.SUPPORTED_BACKENDS:
                errors.append(f"Unsupported backend: {backend_name}")
        
        if spec.algorithm.max_iterations < 1:
            errors.append("max_iterations must be positive")
        
        if spec.algorithm.convergence_threshold <= 0:
            errors.append("convergence_threshold must be positive")
        
        return errors


class DefaultJobPreprocessor:
    """Default job preprocessor implementation."""
    
    async def preprocess(self, spec: JobSpec) -> JobSpec:
        # Normalize algorithm name
        normalized_params = dict(spec.algorithm.algorithm_params)
        
        # Add default parameters if not present
        if "seed" not in normalized_params:
            normalized_params["seed"] = 42
        
        return JobSpec(
            problem=spec.problem,
            algorithm=AlgorithmSettings(
                algorithm_name=spec.algorithm.algorithm_name.lower(),
                max_iterations=spec.algorithm.max_iterations,
                convergence_threshold=spec.algorithm.convergence_threshold,
                algorithm_params=normalized_params,
                warm_start=spec.algorithm.warm_start,
            ),
            backend=BackendSettings(
                backend_name=spec.backend.backend_name.lower(),
                shots=spec.backend.shots,
                optimization_level=spec.backend.optimization_level,
                resilience_level=spec.backend.resilience_level,
                max_execution_time=spec.backend.max_execution_time,
                custom_options=spec.backend.custom_options,
            ) if spec.backend else None,
            crypto=spec.crypto,
            priority=spec.priority,
            tags=spec.tags,
            metadata=spec.metadata,
            owner_id=spec.owner_id,
        )


class DefaultResultAggregator:
    """Default result aggregator implementation."""
    
    async def aggregate(self, results: List[JobResult]) -> JobResult:
        if not results:
            raise ValueError("No results to aggregate")
        
        if len(results) == 1:
            return results[0]
        
        # In a real implementation, this would be more complex
        # For now, just return the first one as a placeholder
        return results[0]


class JobService:
    """
    Service for managing optimization job lifecycle.
    
    Provides operations for submitting, retrieving, cancelling,
    and listing jobs with proper validation and preprocessing.
    """
    
    def __init__(
        self,
        repository: JobStore,
        event_bus: EventBus,
        validator: Optional[JobValidator] = None,
        preprocessor: Optional[JobPreprocessor] = None,
        aggregator: Optional[ResultAggregator] = None,
    ) -> None:
        self._repository = repository
        self._event_bus = event_bus
        self._validator = validator or DefaultJobValidator()
        self._preprocessor = preprocessor or DefaultJobPreprocessor()
        self._aggregator = aggregator or DefaultResultAggregator()
        self._running_jobs: Dict[UUID, asyncio.Task[None]] = {}
    
    async def submit_job(
        self,
        spec: JobSpec,
        tenant_id: str,
    ) -> UUID:
        """
        Submit a new optimization job.
        
        Args:
            spec: Job specification
            tenant_id: Tenant identifier
            
        Returns:
            Job ID
            
        Raises:
            ValueError: If job validation fails
        """
        logger.info(f"Submitting job for tenant {tenant_id}, algorithm: {spec.algorithm.algorithm_name}")
        
        # Validate job spec
        errors = await self._validator.validate(spec, tenant_id)
        if errors:
            error_msg = "; ".join(errors)
            logger.warning(f"Job validation failed: {error_msg}")
            raise ValueError(f"Job validation failed: {error_msg}")
        
        # Preprocess job spec
        processed_spec = await self._preprocessor.preprocess(spec)
        
        # Ensure owner_id is set
        if not processed_spec.owner_id:
            # We can't modify frozen dataclass easily, but JobSpec is NOT frozen
            processed_spec.owner_id = tenant_id
        
        job_id = await self._repository.create_job(processed_spec)
        logger.info(f"Job {job_id} submitted successfully")
        
        # Publish JOB_CREATED event
        await self._event_bus.publish(DomainEvent(
            event_type=EventTypes.JOB_CREATED,
            payload={
                "job_id": str(job_id),
                "tenant_id": tenant_id,
                "algorithm": processed_spec.algorithm.algorithm_name,
            },
            metadata={"tenant_id": tenant_id}
        ))
        
        return job_id
    
    async def get_job_spec(self, job_id: UUID, tenant_id: str) -> Optional[JobSpec]:
        """
        Get a job specification by ID.
        """
        try:
            spec = await self._repository.get_spec(job_id)
            if spec.owner_id != tenant_id:
                logger.warning(f"Unauthorized access attempt to job {job_id} by tenant {tenant_id}")
                return None
            return spec
        except Exception:
            return None
    
    async def get_job_status(self, job_id: UUID, tenant_id: str) -> Optional[JobStatus]:
        """
        Get a job status by ID.
        """
        try:
            spec = await self._repository.get_spec(job_id)
            if spec.owner_id != tenant_id:
                return None
            return await self._repository.get_status(job_id)
        except Exception:
            return None
    
    async def get_job_result(self, job_id: UUID, tenant_id: str) -> Optional[JobResult]:
        """
        Get a job result by ID.
        """
        try:
            spec = await self._repository.get_spec(job_id)
            if spec.owner_id != tenant_id:
                return None
            return await self._repository.get_result(job_id)
        except Exception:
            return None
    
    async def cancel_job(self, job_id: UUID, tenant_id: str) -> bool:
        """
        Cancel a running or pending job.
        """
        try:
            spec = await self._repository.get_spec(job_id)
            if spec.owner_id != tenant_id:
                return False
            
            status = await self._repository.get_status(job_id)
            if status.is_terminal():
                return False
            
            await self._repository.update_status(job_id, JobStatus.CANCELLED)
            logger.info(f"Job {job_id} cancelled")
            return True
        except Exception:
            return False
    
    async def list_jobs(
        self,
        tenant_id: str,
        status: Optional[JobStatus] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[JobSpec]:
        """
        List jobs for a tenant.
        """
        return await self._repository.list_jobs(
            owner_id=tenant_id,
            status=status,
            limit=limit,
            offset=offset,
        )
