"""
Job store port definition.

Defines the protocol for job persistence including specifications,
status tracking, and results.
"""

from datetime import datetime
from typing import Protocol, runtime_checkable
from uuid import UUID

from qsop.domain.models.job import JobResult, JobSpec, JobStatus


@runtime_checkable
class JobStore(Protocol):
    """
    Protocol for job storage and retrieval.

    Provides persistent storage for job specifications, status updates,
    and results.
    """

    async def create_job(self, spec: JobSpec) -> UUID:
        """
        Create a new job from a specification.

        Args:
            spec: The job specification.

        Returns:
            The job ID.

        Raises:
            JobError: If creation fails.
        """
        ...

    async def get_spec(self, job_id: UUID) -> JobSpec:
        """
        Retrieve a job specification.

        Args:
            job_id: The job identifier.

        Returns:
            The job specification.

        Raises:
            JobError: If job not found.
        """
        ...

    async def get_status(self, job_id: UUID) -> JobStatus:
        """
        Get the current status of a job.

        Args:
            job_id: The job identifier.

        Returns:
            The current job status.

        Raises:
            JobError: If job not found.
        """
        ...

    async def update_status(
        self,
        job_id: UUID,
        status: JobStatus,
        error_message: str | None = None,
    ) -> None:
        """
        Update the status of a job.

        Args:
            job_id: The job identifier.
            status: The new status.
            error_message: Optional error message for failed jobs.

        Raises:
            JobError: If update fails or invalid transition.
        """
        ...

    async def store_result(self, result: JobResult) -> None:
        """
        Store a job result.

        Args:
            result: The job result to store.

        Raises:
            JobError: If storage fails.
        """
        ...

    async def get_result(self, job_id: UUID) -> JobResult | None:
        """
        Retrieve a job result.

        Args:
            job_id: The job identifier.

        Returns:
            The job result, or None if not yet available.

        Raises:
            JobError: If retrieval fails.
        """
        ...

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
        """
        List jobs matching the given criteria.

        Args:
            status: Filter by status.
            owner_id: Filter by owner.
            tags: Filter by tags (all must match).
            created_after: Filter by creation time (inclusive).
            created_before: Filter by creation time (exclusive).
            limit: Maximum number of results.
            offset: Number of results to skip.

        Returns:
            List of matching job specifications.

        Raises:
            JobError: If listing fails.
        """
        ...

    async def count_jobs(
        self,
        status: JobStatus | None = None,
        owner_id: str | None = None,
    ) -> int:
        """
        Count jobs matching criteria.

        Args:
            status: Filter by status.
            owner_id: Filter by owner.

        Returns:
            Number of matching jobs.

        Raises:
            JobError: If count fails.
        """
        ...

    async def delete_job(self, job_id: UUID) -> None:
        """
        Delete a job and its associated data.

        Args:
            job_id: The job identifier.

        Raises:
            JobError: If deletion fails.
        """
        ...

    async def get_next_pending(self, priority_order: bool = True) -> JobSpec | None:
        """
        Get the next pending job for execution.

        Args:
            priority_order: If True, return highest priority first.

        Returns:
            The next pending job spec, or None if queue is empty.

        Raises:
            JobError: If retrieval fails.
        """
        ...

    async def mark_started(self, job_id: UUID) -> datetime:
        """
        Mark a job as started.

        Sets the started_at timestamp and updates status to RUNNING.

        Args:
            job_id: The job identifier.

        Returns:
            The start timestamp.

        Raises:
            JobError: If update fails.
        """
        ...

    async def mark_completed(
        self,
        job_id: UUID,
        result_artifact_id: UUID | None = None,
    ) -> datetime:
        """
        Mark a job as completed.

        Sets the completed_at timestamp and updates status to COMPLETED.

        Args:
            job_id: The job identifier.
            result_artifact_id: Optional ID of the result artifact.

        Returns:
            The completion timestamp.

        Raises:
            JobError: If update fails.
        """
        ...
