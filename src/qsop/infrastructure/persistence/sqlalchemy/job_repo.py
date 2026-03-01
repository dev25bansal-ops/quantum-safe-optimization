"""SQLAlchemy repository for job persistence."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from qsop.domain.models.job import (
    AlgorithmSettings,
    BackendSettings,
    JobResult,
    JobSpec,
    JobStatus,
)
from qsop.domain.models.problem import OptimizationProblem

from .models import JobModel


class SQLAlchemyJobRepository:
    """Repository for job CRUD operations using SQLAlchemy."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    def _to_domain_spec(self, model: JobModel) -> JobSpec:
        """Map ORM model to domain JobSpec."""
        return JobSpec(
            id=model.id,
            problem=OptimizationProblem(
                problem_type=model.parameters.get("problem_type", "unknown"),
                data=model.problem_data,
            ),
            algorithm=AlgorithmSettings(
                algorithm_name=model.algorithm,
                max_iterations=model.parameters.get("max_iterations", 100),
                convergence_threshold=model.parameters.get("convergence_threshold", 1e-6),
                algorithm_params=model.parameters,
            ),
            backend=BackendSettings(
                backend_name=model.backend,
            )
            if model.backend
            else None,
            priority=model.priority,
            owner_id=model.tenant_id,
            created_at=model.created_at,
            metadata={
                "name": model.name,
                "callback_url": model.callback_url,
                "progress": model.progress,
            },
        )

    def _to_domain_result(self, model: JobModel) -> JobResult | None:
        """Map ORM model to domain JobResult."""
        if model.status != "completed" and model.status != "failed":
            return None

        return JobResult(
            job_id=model.id,
            status=JobStatus(model.status),
            error_message=model.error_message,
            started_at=model.started_at,
            completed_at=model.completed_at,
            metadata={
                "progress": model.progress,
            },
        )

    # API Router compatibility methods
    async def create(
        self,
        tenant_id: str,
        algorithm: str,
        backend: str,
        parameters: dict[str, Any],
        problem_data: dict[str, Any],
        name: str | None = None,
        priority: int = 5,
        callback_url: str | None = None,
    ) -> JobModel:
        """Create a new job."""
        job = JobModel(
            tenant_id=tenant_id,
            name=name,
            algorithm=algorithm,
            backend=backend,
            parameters=parameters,
            problem_data=problem_data,
            priority=priority,
            callback_url=callback_url,
            status="pending",
        )
        self.session.add(job)
        await self.session.flush()
        await self.session.refresh(job)
        return job

    async def get_by_id(
        self,
        job_id: UUID,
        tenant_id: str | None = None,
    ) -> JobModel | None:
        """Get a job by ID, optionally filtering by tenant."""
        stmt = select(JobModel).where(
            JobModel.id == job_id,
            JobModel.deleted_at.is_(None),
        )
        if tenant_id:
            stmt = stmt.where(JobModel.tenant_id == tenant_id)

        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_by_tenant(
        self,
        tenant_id: str,
        status: str | None = None,
        limit: int = 20,
        offset: int = 0,
    ) -> tuple[list[JobModel], int]:
        """List jobs for a tenant with pagination."""
        # Base query
        base_query = select(JobModel).where(
            JobModel.tenant_id == tenant_id,
            JobModel.deleted_at.is_(None),
        )

        if status:
            base_query = base_query.where(JobModel.status == status)

        # Count query
        count_stmt = select(func.count()).select_from(base_query.subquery())
        total_result = await self.session.execute(count_stmt)
        total = total_result.scalar() or 0

        # Data query with pagination
        stmt = base_query.order_by(JobModel.created_at.desc()).limit(limit).offset(offset)
        result = await self.session.execute(stmt)
        jobs = list(result.scalars().all())

        return jobs, total

    # JobStore Port Implementation
    async def create_job(self, spec: JobSpec) -> UUID:
        """Create a new job from a specification."""
        job = await self.create(
            tenant_id=spec.owner_id or "default",
            algorithm=spec.algorithm.algorithm_name,
            backend=spec.backend.backend_name if spec.backend else "simulator",
            parameters=spec.algorithm.algorithm_params,
            problem_data=spec.problem.data,
            name=spec.metadata.get("name"),
            priority=spec.priority,
            callback_url=spec.metadata.get("callback_url"),
        )
        return job.id

    async def get_spec(self, job_id: UUID) -> JobSpec:
        """Retrieve a job specification."""
        job = await self.get_by_id(job_id)
        if not job:
            raise ValueError(f"Job {job_id} not found")
        return self._to_domain_spec(job)

    async def get_status(self, job_id: UUID) -> JobStatus:
        """Get the current status of a job."""
        job = await self.get_by_id(job_id)
        if not job:
            raise ValueError(f"Job {job_id} not found")
        return JobStatus(job.status)

    async def update_status(
        self,
        job_id: UUID,
        status: JobStatus | str,
        error_message: str | None = None,
        progress: float | None = None,
    ) -> JobModel | None:
        """Update job status."""
        status_val = status.value if isinstance(status, JobStatus) else status
        update_data: dict[str, Any] = {"status": status_val}

        if error_message is not None:
            update_data["error_message"] = error_message
        if progress is not None:
            update_data["progress"] = progress

        # Set timing fields based on status
        now = datetime.utcnow()
        if status_val == "running":
            update_data["started_at"] = now
        elif status_val in ("completed", "failed", "cancelled"):
            update_data["completed_at"] = now

        stmt = (
            update(JobModel).where(JobModel.id == job_id).values(**update_data).returning(JobModel)
        )
        result = await self.session.execute(stmt)
        await self.session.flush()
        return result.scalar_one_or_none()

    async def store_result(self, result: JobResult) -> None:
        """Store a job result."""
        await self.update_status(
            job_id=result.job_id,
            status=result.status,
            error_message=result.error_message,
        )

    async def get_result(self, job_id: UUID) -> JobResult | None:
        """Retrieve a job result."""
        job = await self.get_by_id(job_id)
        if not job:
            return None
        return self._to_domain_result(job)

    async def list_jobs(
        self,
        status: JobStatus | None = None,
        owner_id: str | None = None,
        tags: tuple[str, ...] | None = None,
        created_after: datetime | None = None,
        created_before: datetime | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[JobSpec]:
        """List jobs matching the given criteria."""
        stmt = select(JobModel).where(JobModel.deleted_at.is_(None))

        if status:
            stmt = stmt.where(JobModel.status == status.value)
        if owner_id:
            stmt = stmt.where(JobModel.tenant_id == owner_id)
        if created_after:
            stmt = stmt.where(JobModel.created_at >= created_after)
        if created_before:
            stmt = stmt.where(JobModel.created_at < created_before)

        stmt = stmt.order_by(JobModel.created_at.desc()).limit(limit).offset(offset)
        result = await self.session.execute(stmt)
        return [self._to_domain_spec(row) for row in result.scalars().all()]

    async def count_jobs(
        self,
        status: JobStatus | None = None,
        owner_id: str | None = None,
    ) -> int:
        """Count jobs matching criteria."""
        stmt = select(func.count()).select_from(JobModel).where(JobModel.deleted_at.is_(None))
        if status:
            stmt = stmt.where(JobModel.status == status.value)
        if owner_id:
            stmt = stmt.where(JobModel.tenant_id == owner_id)

        result = await self.session.execute(stmt)
        return result.scalar() or 0

    async def delete_job(self, job_id: UUID) -> None:
        """Delete a job and its associated data."""
        stmt = update(JobModel).where(JobModel.id == job_id).values(deleted_at=datetime.utcnow())
        await self.session.execute(stmt)
        await self.session.flush()

    async def get_next_pending(self, priority_order: bool = True) -> JobSpec | None:
        """Get the next pending job for execution."""
        stmt = select(JobModel).where(
            JobModel.status == "pending",
            JobModel.deleted_at.is_(None),
        )
        if priority_order:
            stmt = stmt.order_by(JobModel.priority.desc(), JobModel.created_at.asc())
        else:
            stmt = stmt.order_by(JobModel.created_at.asc())

        stmt = stmt.limit(1)
        result = await self.session.execute(stmt)
        job = result.scalar_one_or_none()
        return self._to_domain_spec(job) if job else None

    async def mark_started(self, job_id: UUID) -> datetime:
        """Mark a job as started."""
        now = datetime.utcnow()
        await self.update_status(job_id, JobStatus.RUNNING, progress=0.0)
        return now

    async def mark_completed(
        self,
        job_id: UUID,
        result_artifact_id: UUID | None = None,
    ) -> datetime:
        """Mark a job as completed."""
        now = datetime.utcnow()
        await self.update_status(job_id, JobStatus.COMPLETED, progress=100.0)
        return now

    async def update_progress(
        self,
        job_id: UUID,
        progress: float,
        estimated_completion: datetime | None = None,
    ) -> None:
        """Update job progress."""
        update_data: dict[str, Any] = {"progress": progress}
        if estimated_completion:
            update_data["estimated_completion"] = estimated_completion

        stmt = update(JobModel).where(JobModel.id == job_id).values(**update_data)
        await self.session.execute(stmt)
        await self.session.flush()

    async def soft_delete(self, job_id: UUID, tenant_id: str) -> bool:
        """Soft delete a job."""
        stmt = (
            update(JobModel)
            .where(
                JobModel.id == job_id,
                JobModel.tenant_id == tenant_id,
                JobModel.deleted_at.is_(None),
            )
            .values(deleted_at=datetime.utcnow())
        )
        result = await self.session.execute(stmt)
        await self.session.flush()
        return result.rowcount > 0

    async def get_pending_jobs(
        self,
        limit: int = 10,
    ) -> list[JobModel]:
        """Get pending jobs ordered by priority and creation time."""
        stmt = (
            select(JobModel)
            .where(
                JobModel.status == "pending",
                JobModel.deleted_at.is_(None),
            )
            .order_by(
                JobModel.priority.desc(),
                JobModel.created_at.asc(),
            )
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_stale_running_jobs(
        self,
        stale_threshold_minutes: int = 60,
    ) -> list[JobModel]:
        """Get running jobs that may be stale/stuck."""
        threshold = datetime.utcnow()
        # Calculate threshold based on minutes
        from datetime import timedelta

        threshold = threshold - timedelta(minutes=stale_threshold_minutes)

        stmt = select(JobModel).where(
            JobModel.status == "running",
            JobModel.started_at < threshold,
            JobModel.deleted_at.is_(None),
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())
