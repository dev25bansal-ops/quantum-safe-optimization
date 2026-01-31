"""SQLAlchemy repository for job persistence."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import select, update, func
from sqlalchemy.ext.asyncio import AsyncSession

from .models import JobModel


class SQLAlchemyJobRepository:
    """Repository for job CRUD operations using SQLAlchemy."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

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
        stmt = (
            base_query
            .order_by(JobModel.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        result = await self.session.execute(stmt)
        jobs = list(result.scalars().all())
        
        return jobs, total

    async def update_status(
        self,
        job_id: UUID,
        status: str,
        error_message: str | None = None,
        progress: float | None = None,
    ) -> JobModel | None:
        """Update job status."""
        update_data: dict[str, Any] = {"status": status}
        
        if error_message is not None:
            update_data["error_message"] = error_message
        if progress is not None:
            update_data["progress"] = progress
        
        # Set timing fields based on status
        now = datetime.utcnow()
        if status == "running":
            update_data["started_at"] = now
        elif status in ("completed", "failed", "cancelled"):
            update_data["completed_at"] = now
        
        stmt = (
            update(JobModel)
            .where(JobModel.id == job_id)
            .values(**update_data)
            .returning(JobModel)
        )
        result = await self.session.execute(stmt)
        await self.session.flush()
        return result.scalar_one_or_none()

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
        
        stmt = (
            update(JobModel)
            .where(JobModel.id == job_id)
            .values(**update_data)
        )
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
        
        stmt = (
            select(JobModel)
            .where(
                JobModel.status == "running",
                JobModel.started_at < threshold,
                JobModel.deleted_at.is_(None),
            )
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())
