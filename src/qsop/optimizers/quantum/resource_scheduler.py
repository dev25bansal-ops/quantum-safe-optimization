"""
Quantum Resource Scheduler Module.

Provides intelligent scheduling and resource allocation for quantum jobs
across multiple backends with priority management, cost optimization,
and deadline-aware scheduling.
"""

import logging
import asyncio
from typing import Any, Dict, List, Optional, Tuple, Callable
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime, timedelta
from collections import defaultdict
import heapq

logger = logging.getLogger(__name__)


class JobPriority(Enum):
    """Job priority levels."""
    URGENT = 0
    HIGH = 1
    NORMAL = 2
    LOW = 3
    BACKGROUND = 4


class JobStatus(Enum):
    """Job status in the scheduler."""
    PENDING = "pending"
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    TIMEOUT = "timeout"


class BackendStatus(Enum):
    """Backend availability status."""
    AVAILABLE = "available"
    BUSY = "busy"
    OFFLINE = "offline"
    MAINTENANCE = "maintenance"


@dataclass
class QuantumBackend:
    """Represents a quantum computing backend."""
    
    backend_id: str
    name: str
    provider: str
    max_qubits: int
    max_jobs: int
    cost_per_hour: float
    status: BackendStatus = BackendStatus.AVAILABLE
    current_jobs: int = 0
    avg_queue_time: float = 0.0
    success_rate: float = 1.0
    
    @property
    def available_capacity(self) -> int:
        """Get available job capacity."""
        return max(0, self.max_jobs - self.current_jobs)
    
    @property
    def utilization(self) -> float:
        """Get backend utilization (0-1)."""
        return self.current_jobs / self.max_jobs if self.max_jobs > 0 else 0.0
    
    def can_accept_job(self, num_qubits: int) -> bool:
        """Check if backend can accept a job."""
        return (
            self.status == BackendStatus.AVAILABLE
            and num_qubits <= self.max_qubits
            and self.available_capacity > 0
        )


@dataclass
class ScheduledJob:
    """Represents a scheduled quantum job."""
    
    job_id: str
    user_id: str
    problem_type: str
    num_qubits: int
    estimated_duration: float  # in seconds
    priority: JobPriority
    deadline: Optional[datetime] = None
    created_at: datetime = field(default_factory=datetime.now)
    scheduled_at: Optional[datetime] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    status: JobStatus = JobStatus.PENDING
    assigned_backend: Optional[str] = None
    retry_count: int = 0
    max_retries: int = 3
    
    @property
    def age(self) -> timedelta:
        """Get job age."""
        return datetime.now() - self.created_at
    
    @property
    def time_until_deadline(self) -> Optional[timedelta]:
        """Get time until deadline."""
        if self.deadline is None:
            return None
        return self.deadline - datetime.now()
    
    @property
    def is_overdue(self) -> bool:
        """Check if job is overdue."""
        if self.deadline is None:
            return False
        return datetime.now() > self.deadline
    
    @property
    def can_retry(self) -> bool:
        """Check if job can be retried."""
        return self.retry_count < self.max_retries


class SchedulingStrategy:
    """Base class for scheduling strategies."""
    
    def select_backend(
        self,
        job: ScheduledJob,
        backends: List[QuantumBackend]
    ) -> Optional[QuantumBackend]:
        """Select the best backend for a job."""
        raise NotImplementedError


class PriorityStrategy(SchedulingStrategy):
    """Priority-based scheduling strategy."""
    
    def select_backend(
        self,
        job: ScheduledJob,
        backends: List[QuantumBackend]
    ) -> Optional[QuantumBackend]:
        """Select backend based on job priority and availability."""
        # Filter available backends
        available = [
            b for b in backends
            if b.can_accept_job(job.num_qubits)
        ]
        
        if not available:
            return None
        
        # Sort by utilization (prefer less utilized backends)
        available.sort(key=lambda b: b.utilization)
        
        return available[0]


class CostOptimizationStrategy(SchedulingStrategy):
    """Cost-optimization scheduling strategy."""
    
    def select_backend(
        self,
        job: ScheduledJob,
        backends: List[QuantumBackend]
    ) -> Optional[QuantumBackend]:
        """Select backend based on cost optimization."""
        # Filter available backends
        available = [
            b for b in backends
            if b.can_accept_job(job.num_qubits)
        ]
        
        if not available:
            return None
        
        # Calculate cost for each backend
        def calculate_cost(backend: QuantumBackend) -> float:
            duration_hours = job.estimated_duration / 3600
            return backend.cost_per_hour * duration_hours
        
        # Sort by cost (prefer cheaper backends)
        available.sort(key=calculate_cost)
        
        return available[0]


class DeadlineAwareStrategy(SchedulingStrategy):
    """Deadline-aware scheduling strategy."""
    
    def select_backend(
        self,
        job: ScheduledJob,
        backends: List[QuantumBackend]
    ) -> Optional[QuantumBackend]:
        """Select backend considering job deadline."""
        if job.deadline is None:
            # No deadline, use priority strategy
            return PriorityStrategy().select_backend(job, backends)
        
        # Filter available backends
        available = [
            b for b in backends
            if b.can_accept_job(job.num_qubits)
        ]
        
        if not available:
            return None
        
        # Calculate estimated completion time for each backend
        def estimate_completion(backend: QuantumBackend) -> datetime:
            queue_time = backend.avg_queue_time * backend.current_jobs
            start_time = datetime.now() + timedelta(seconds=queue_time)
            completion_time = start_time + timedelta(seconds=job.estimated_duration)
            return completion_time
        
        # Filter backends that can meet deadline
        can_meet_deadline = [
            b for b in available
            if estimate_completion(b) <= job.deadline
        ]
        
        if can_meet_deadline:
            # Among those, prefer cheapest
            return CostOptimizationStrategy().select_backend(job, can_meet_deadline)
        else:
            # Can't meet deadline, use fastest available
            available.sort(key=lambda b: b.avg_queue_time)
            return available[0]


class HybridStrategy(SchedulingStrategy):
    """Hybrid scheduling strategy combining multiple approaches."""
    
    def __init__(self):
        self.strategies = [
            DeadlineAwareStrategy(),
            CostOptimizationStrategy(),
            PriorityStrategy()
        ]
    
    def select_backend(
        self,
        job: ScheduledJob,
        backends: List[QuantumBackend]
    ) -> Optional[QuantumBackend]:
        """Select backend using hybrid approach."""
        for strategy in self.strategies:
            backend = strategy.select_backend(job, backends)
            if backend is not None:
                return backend
        return None


class QuantumResourceScheduler:
    """Main scheduler for quantum job resources."""
    
    def __init__(
        self,
        strategy: Optional[SchedulingStrategy] = None,
        max_queue_size: int = 1000
    ):
        self.strategy = strategy or HybridStrategy()
        self.max_queue_size = max_queue_size
        
        # Job queues by priority
        self._queues: Dict[JobPriority, List[ScheduledJob]] = {
            priority: [] for priority in JobPriority
        }
        
        # Backends
        self._backends: Dict[str, QuantumBackend] = {}
        
        # Running jobs
        self._running_jobs: Dict[str, ScheduledJob] = {}
        
        # Job history
        self._job_history: List[ScheduledJob] = []
        
        # Statistics
        self._stats = {
            "jobs_submitted": 0,
            "jobs_completed": 0,
            "jobs_failed": 0,
            "jobs_cancelled": 0,
            "total_wait_time": 0.0,
            "total_execution_time": 0.0,
        }
        
        # Scheduler state
        self._running = False
        self._scheduler_task: Optional[asyncio.Task] = None
    
    def register_backend(self, backend: QuantumBackend) -> None:
        """Register a quantum backend."""
        self._backends[backend.backend_id] = backend
        logger.info(f"Registered backend: {backend.name} ({backend.backend_id})")
    
    def unregister_backend(self, backend_id: str) -> None:
        """Unregister a quantum backend."""
        if backend_id in self._backends:
            del self._backends[backend_id]
            logger.info(f"Unregistered backend: {backend_id}")
    
    def get_backend(self, backend_id: str) -> Optional[QuantumBackend]:
        """Get a backend by ID."""
        return self._backends.get(backend_id)
    
    def get_all_backends(self) -> List[QuantumBackend]:
        """Get all registered backends."""
        return list(self._backends.values())
    
    def get_available_backends(self, num_qubits: int) -> List[QuantumBackend]:
        """Get available backends for a given qubit count."""
        return [
            b for b in self._backends.values()
            if b.can_accept_job(num_qubits)
        ]
    
    async def submit_job(
        self,
        job_id: str,
        user_id: str,
        problem_type: str,
        num_qubits: int,
        estimated_duration: float,
        priority: JobPriority = JobPriority.NORMAL,
        deadline: Optional[datetime] = None
    ) -> ScheduledJob:
        """Submit a job to the scheduler."""
        
        # Check queue capacity
        total_queued = sum(len(queue) for queue in self._queues.values())
        if total_queued >= self.max_queue_size:
            raise RuntimeError("Scheduler queue is full")
        
        # Create scheduled job
        job = ScheduledJob(
            job_id=job_id,
            user_id=user_id,
            problem_type=problem_type,
            num_qubits=num_qubits,
            estimated_duration=estimated_duration,
            priority=priority,
            deadline=deadline
        )
        
        # Add to appropriate queue
        self._queues[priority].append(job)
        job.status = JobStatus.QUEUED
        job.scheduled_at = datetime.now()
        
        # Update statistics
        self._stats["jobs_submitted"] += 1
        
        logger.info(
            f"Job {job_id} submitted with priority {priority.value} "
            f"(qubits: {num_qubits}, duration: {estimated_duration}s)"
        )
        
        return job
    
    async def cancel_job(self, job_id: str) -> bool:
        """Cancel a queued or running job."""
        
        # Check running jobs
        if job_id in self._running_jobs:
            job = self._running_jobs[job_id]
            job.status = JobStatus.CANCELLED
            job.completed_at = datetime.now()
            del self._running_jobs[job_id]
            
            # Free up backend capacity
            if job.assigned_backend:
                backend = self._backends.get(job.assigned_backend)
                if backend:
                    backend.current_jobs -= 1
            
            self._stats["jobs_cancelled"] += 1
            logger.info(f"Cancelled running job: {job_id}")
            return True
        
        # Check queued jobs
        for priority, queue in self._queues.items():
            for i, job in enumerate(queue):
                if job.job_id == job_id:
                    job.status = JobStatus.CANCELLED
                    job.completed_at = datetime.now()
                    queue.pop(i)
                    
                    self._stats["jobs_cancelled"] += 1
                    logger.info(f"Cancelled queued job: {job_id}")
                    return True
        
        return False
    
    async def get_job_status(self, job_id: str) -> Optional[ScheduledJob]:
        """Get the status of a job."""
        
        # Check running jobs
        if job_id in self._running_jobs:
            return self._running_jobs[job_id]
        
        # Check queued jobs
        for queue in self._queues.values():
            for job in queue:
                if job.job_id == job_id:
                    return job
        
        # Check history
        for job in self._job_history:
            if job.job_id == job_id:
                return job
        
        return None
    
    async def list_user_jobs(
        self,
        user_id: str,
        status: Optional[JobStatus] = None
    ) -> List[ScheduledJob]:
        """List jobs for a user."""
        jobs = []
        
        # Check running jobs
        for job in self._running_jobs.values():
            if job.user_id == user_id:
                if status is None or job.status == status:
                    jobs.append(job)
        
        # Check queued jobs
        for queue in self._queues.values():
            for job in queue:
                if job.user_id == user_id:
                    if status is None or job.status == status:
                        jobs.append(job)
        
        # Check history
        for job in self._job_history:
            if job.user_id == user_id:
                if status is None or job.status == status:
                    jobs.append(job)
        
        return jobs
    
    async def _schedule_next_job(self) -> Optional[Tuple[ScheduledJob, QuantumBackend]]:
        """Schedule the next job from the queue."""
        
        # Check queues in priority order
        for priority in sorted(JobPriority):
            queue = self._queues[priority]
            
            if not queue:
                continue
            
            # Get next job
            job = queue[0]
            
            # Find available backend
            backend = self.strategy.select_backend(job, list(self._backends.values()))
            
            if backend is None:
                continue
            
            # Remove from queue
            queue.pop(0)
            
            # Assign backend
            job.assigned_backend = backend.backend_id
            job.status = JobStatus.RUNNING
            job.started_at = datetime.now()
            
            # Update backend
            backend.current_jobs += 1
            
            # Add to running jobs
            self._running_jobs[job.job_id] = job
            
            logger.info(
                f"Scheduled job {job.job_id} on backend {backend.name} "
                f"(priority: {priority.value})"
            )
            
            return job, backend
        
        return None
    
    async def _complete_job(self, job: ScheduledJob, success: bool = True) -> None:
        """Mark a job as completed."""
        
        # Update job status
        job.status = JobStatus.COMPLETED if success else JobStatus.FAILED
        job.completed_at = datetime.now()
        
        # Remove from running jobs
        if job.job_id in self._running_jobs:
            del self._running_jobs[job.job_id]
        
        # Free up backend capacity
        if job.assigned_backend:
            backend = self._backends.get(job.assigned_backend)
            if backend:
                backend.current_jobs -= 1
        
        # Add to history
        self._job_history.append(job)
        
        # Update statistics
        if success:
            self._stats["jobs_completed"] += 1
        else:
            self._stats["jobs_failed"] += 1
        
        # Calculate execution time
        if job.started_at and job.completed_at:
            execution_time = (job.completed_at - job.started_at).total_seconds()
            self._stats["total_execution_time"] += execution_time
        
        logger.info(
            f"Job {job.job_id} completed "
            f"({'success' if success else 'failed'}) "
            f"in {job.completed_at - job.started_at if job.started_at else 'N/A'}"
        )
    
    async def _retry_job(self, job: ScheduledJob) -> bool:
        """Retry a failed job."""
        
        if not job.can_retry:
            return False
        
        # Increment retry count
        job.retry_count += 1
        
        # Reset job status
        job.status = JobStatus.PENDING
        job.assigned_backend = None
        job.started_at = None
        
        # Re-queue with same priority
        self._queues[job.priority].append(job)
        
        logger.info(f"Retrying job {job.job_id} (attempt {job.retry_count})")
        
        return True
    
    async def start(self) -> None:
        """Start the scheduler."""
        if self._running:
            logger.warning("Scheduler is already running")
            return
        
        self._running = True
        self._scheduler_task = asyncio.create_task(self._scheduler_loop())
        logger.info("Scheduler started")
    
    async def stop(self) -> None:
        """Stop the scheduler."""
        if not self._running:
            logger.warning("Scheduler is not running")
            return
        
        self._running = False
        
        if self._scheduler_task:
            self._scheduler_task.cancel()
            try:
                await self._scheduler_task
            except asyncio.CancelledError:
                pass
        
        logger.info("Scheduler stopped")
    
    async def _scheduler_loop(self) -> None:
        """Main scheduler loop."""
        while self._running:
            try:
                # Schedule next job
                result = await self._schedule_next_job()
                
                if result is None:
                    # No jobs to schedule, wait a bit
                    await asyncio.sleep(1.0)
                else:
                    job, backend = result
                    
                    # Simulate job execution (in real implementation, this would
                    # actually run the quantum job and wait for completion)
                    await asyncio.sleep(job.estimated_duration)
                    
                    # Mark job as completed
                    await self._complete_job(job, success=True)
            
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Scheduler loop error: {e}")
                await asyncio.sleep(1.0)
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get scheduler statistics."""
        total_queued = sum(len(queue) for queue in self._queues.values())
        
        avg_wait_time = 0.0
        if self._stats["jobs_completed"] > 0:
            avg_wait_time = self._stats["total_wait_time"] / self._stats["jobs_completed"]
        
        avg_execution_time = 0.0
        if self._stats["jobs_completed"] > 0:
            avg_execution_time = self._stats["total_execution_time"] / self._stats["jobs_completed"]
        
        return {
            **self._stats,
            "jobs_queued": total_queued,
            "jobs_running": len(self._running_jobs),
            "backends_registered": len(self._backends),
            "backends_available": len([b for b in self._backends.values() if b.status == BackendStatus.AVAILABLE]),
            "avg_wait_time": avg_wait_time,
            "avg_execution_time": avg_execution_time,
        }
    
    def get_queue_status(self) -> Dict[JobPriority, int]:
        """Get queue status by priority."""
        return {
            priority: len(queue)
            for priority, queue in self._queues.items()
        }


# Factory function
def create_scheduler(
    strategy: Optional[SchedulingStrategy] = None,
    max_queue_size: int = 1000
) -> QuantumResourceScheduler:
    """Create a quantum resource scheduler."""
    return QuantumResourceScheduler(strategy, max_queue_size)