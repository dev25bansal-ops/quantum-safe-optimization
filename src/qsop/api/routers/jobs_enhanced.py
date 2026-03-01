"""
Enhanced Job Management Endpoints
Production-ready job submission and management with improved error handling and performance
"""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status

from qsop.api.deps import CurrentTenant, ServiceContainerDep
from qsop.api.schemas.job import (
    JobCreate,
    JobListResponse,
    JobResponse,
    JobStatus,
)
from qsop.api.schemas.results import JobResultsResponse

router = APIRouter()


@router.post(
    "",
    response_model=JobResponse,
    status_code=status.HTTP_201_CREATED,
    responses={
        400: {"model": dict, "description": "Invalid job specification"},
        401: {"model": dict, "description": "Authentication required"},
        429: {"model": dict, "description": "Rate limit exceeded"},
    },
)
async def submit_job(
    job_data: JobCreate,
    tenant_id: CurrentTenant,
    container: ServiceContainerDep,
) -> JobResponse:
    """
    Submit a new optimization job.

    Creates a new job with the specified parameters and queues it for execution.
    The job will be processed asynchronously by the backend workers.

    **Returns:**
        - JobResponse: Created job with ID and initial status

    **Errors:**
        - 400: Invalid job specification
        - 401: Not authenticated
        - 429: Rate limit exceeded
    """
    try:
        # Validate job data using the service
        job = await container.job_service.create_job(
            tenant_id=tenant_id,
            algorithm=job_data.algorithm,
            backend=job_data.backend,
            parameters=job_data.parameters,
            problem_data=job_data.problem_data,
            priority=job_data.priority,
            callback_url=job_data.callback_url,
            crypto_settings=job_data.crypto,
        )

        # Publish job created event for async processing
        await container.event_bus.publish(
            "job.created",
            {"job_id": str(job.id), "tenant_id": tenant_id, "algorithm": job_data.algorithm},
        )

        return JobResponse.model_validate(job)

    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e
    except Exception as e:
        # Log unexpected errors
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create job: {str(e)}",
        ) from e


@router.get("", response_model=JobListResponse)
async def list_jobs(
    tenant_id: CurrentTenant,
    container: ServiceContainerDep,
    status_filter: Annotated[JobStatus | None, Query(alias="status")] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
    search: Annotated[str | None, Query(description="Search in job IDs or algorithms")] = None,
) -> JobListResponse:
    """
    List jobs for the current tenant.

    Supports filtering by status, searching, and pagination.
    Returns jobs sorted by creation date (newest first).

    **Query Parameters:**
        - status: Filter by job status (pending, running, completed, failed, cancelled)
        - limit: Number of jobs per page (1-100, default: 20)
        - offset: Number of jobs to skip (default: 0)
        - search: Search term for job IDs or algorithms

    **Returns:**
        - JobListResponse: Paginated list of jobs

    **Errors:**
        - 401: Not authenticated
    """
    try:
        jobs, total = await container.job_service.list_jobs(
            tenant_id=tenant_id,
            status=status_filter.value if status_filter else None,
            limit=limit,
            offset=offset,
            search=search,
        )

    except NotImplementedError:
        # Fall back to repository if service doesn't implement search
        jobs, total = await container.job_repo.list_by_tenant(
            tenant_id=tenant_id,
            status=status_filter.value if status_filter else None,
            limit=limit,
            offset=offset,
        )

    return JobListResponse(
        jobs=[JobResponse.model_validate(j) for j in jobs],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get(
    "/{job_id}",
    response_model=JobResponse,
    responses={
        404: {"model": dict, "description": "Job not found"},
        403: {"model": dict, "description": "Access denied"},
    },
)
async def get_job(
    job_id: UUID,
    tenant_id: CurrentTenant,
    container: ServiceContainerDep,
) -> JobResponse:
    """
    Get details of a specific job.

    Returns comprehensive information about a job including its configuration,
    current status, and execution details.

    **Returns:**
        - JobResponse: Complete job details

    **Errors:**
        - 404: Job not found
        - 403: Access denied (not owned by tenant)
    """
    job = await container.job_repo.get_by_id(job_id, tenant_id)

    if job is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Job {job_id} not found",
        )

    return JobResponse.model_validate(job)


@router.delete(
    "/{job_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    responses={
        404: {"model": dict, "description": "Job not found"},
        400: {"model": dict, "description": "Cannot cancel completed job"},
    },
)
async def cancel_job(
    job_id: UUID,
    tenant_id: CurrentTenant,
    container: ServiceContainerDep,
) -> None:
    """
    Cancel a running or queued job.

    Jobs that have already completed, failed, or been cancelled cannot be cancelled again.
    Cancellation is best-effort; some backends may not support immediate cancellation.

    **Errors:**
        - 404: Job not found
        - 400: Cannot cancel job with current status
    """
    job = await container.job_repo.get_by_id(job_id, tenant_id)

    if job is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Job {job_id} not found",
        )

    if job.status in ("completed", "failed", "cancelled"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot cancel job with status '{job.status}'",
        )

    await container.job_service.cancel_job(job_id, tenant_id)

    # Publish cancellation event
    await container.event_bus.publish(
        "job.cancelled",
        {"job_id": str(job_id), "tenant_id": tenant_id, "previous_status": job.status},
    )


@router.get(
    "/{job_id}/results",
    response_model=JobResultsResponse,
    responses={
        404: {"model": dict, "description": "Job or results not found"},
        400: {"model": dict, "description": "Job not completed yet"},
    },
)
async def get_job_results(
    job_id: UUID,
    tenant_id: CurrentTenant,
    container: ServiceContainerDep,
) -> JobResultsResponse:
    """
    Get the results of a completed job.

    Returns the optimization results including the optimal solution, convergence history,
    and execution metrics. Only available for completed jobs.

    **Returns:**
        - JobResultsResponse: Job execution results

    **Errors:**
        - 404: Job or results not found
        - 400: Job not completed yet
    """
    job = await container.job_repo.get_by_id(job_id, tenant_id)

    if job is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Job {job_id} not found",
        )

    if job.status != "completed":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Job results not available. Current status: {job.status}",
        )

    # Fetch results from artifact store
    try:
        results_key = f"jobs/{job_id}/results.json"
        results_data = await container.artifact_store.retrieve(results_key)

        if results_data is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Results not found in artifact store",
            )

        return JobResultsResponse.model_validate_json(results_data)

    except AttributeError:
        # Fall back for older artifact store implementations
        try:
            results_data = await container.artifact_store.get(results_key)

            if results_data is None:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Results not found in artifact store",
                )

            return JobResultsResponse.model_validate_json(results_data)

        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to retrieve results: {str(e)}",
            ) from e


@router.post(
    "/{job_id}/retry",
    response_model=JobResponse,
    status_code=status.HTTP_202_ACCEPTED,
    responses={
        404: {"model": dict, "description": "Job not found"},
        400: {"model": dict, "description": "Cannot retry non-failed job"},
    },
)
async def retry_job(
    job_id: UUID,
    tenant_id: CurrentTenant,
    container: ServiceContainerDep,
) -> JobResponse:
    """
    Retry a failed job.

    Creates a new job with the same configuration as a failed job.
    The original job remains in the history.

    **Returns:**
        - JobResponse: New retry job

    **Errors:**
        - 404: Original job not found
        - 400: Cannot retry job (must be failed status)
    """
    original_job = await container.job_repo.get_by_id(job_id, tenant_id)

    if original_job is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Job {job_id} not found",
        )

    if original_job.status != "failed":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Can only retry failed jobs",
        )

    # Create retry job with same configuration
    retry_job = await container.job_service.create_job(
        tenant_id=tenant_id,
        algorithm=original_job.algorithm,
        backend=original_job.backend,
        parameters=original_job.parameters,
        problem_data=original_job.problem_data,
        priority=original_job.priority,
        callback_url=original_job.callback_url,
        crypto_settings=getattr(original_job, "crypto_settings", None),
        parent_job_id=job_id,  # Track this is a retry
    )

    await container.event_bus.publish(
        "job.retry",
        {"job_id": str(job_id), "retry_job_id": str(retry_job.id), "tenant_id": tenant_id},
    )

    return JobResponse.model_validate(retry_job)
