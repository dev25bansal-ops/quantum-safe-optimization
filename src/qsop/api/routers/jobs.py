"""Job management endpoints."""

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


@router.post("", response_model=JobResponse, status_code=status.HTTP_201_CREATED)
async def submit_job(
    job_data: JobCreate,
    tenant_id: CurrentTenant,
    container: ServiceContainerDep,
) -> JobResponse:
    """
    Submit a new optimization job.

    Creates a new job with the specified parameters and queues it for execution.
    """
    try:
        job = await container.job_repo.create(
            tenant_id=tenant_id,
            algorithm=job_data.algorithm,
            backend=job_data.backend,
            parameters=job_data.parameters,
            problem_data=job_data.problem_data,
        )

        # Publish job created event
        await container.event_bus.publish(
            "job.created",
            {"job_id": str(job.id), "tenant_id": tenant_id},
        )

        return JobResponse.model_validate(job)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.get("", response_model=JobListResponse)
async def list_jobs(
    tenant_id: CurrentTenant,
    container: ServiceContainerDep,
    status_filter: Annotated[JobStatus | None, Query(alias="status")] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> JobListResponse:
    """
    List jobs for the current tenant.

    Supports filtering by status and pagination.
    """
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


@router.get("/{job_id}", response_model=JobResponse)
async def get_job(
    job_id: UUID,
    tenant_id: CurrentTenant,
    container: ServiceContainerDep,
) -> JobResponse:
    """
    Get details of a specific job.
    """
    job = await container.job_repo.get_by_id(job_id, tenant_id)

    if job is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Job {job_id} not found",
        )

    return JobResponse.model_validate(job)


@router.delete("/{job_id}", status_code=status.HTTP_204_NO_CONTENT)
async def cancel_job(
    job_id: UUID,
    tenant_id: CurrentTenant,
    container: ServiceContainerDep,
) -> None:
    """
    Cancel a running or queued job.

    Jobs that have already completed cannot be cancelled.
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

    await container.job_repo.update_status(job_id, "cancelled")

    # Publish cancellation event
    await container.event_bus.publish(
        "job.cancelled",
        {"job_id": str(job_id), "tenant_id": tenant_id},
    )


@router.get("/{job_id}/results", response_model=JobResultsResponse)
async def get_job_results(
    job_id: UUID,
    tenant_id: CurrentTenant,
    container: ServiceContainerDep,
) -> JobResultsResponse:
    """
    Get the results of a completed job.

    Returns 404 if the job doesn't exist or hasn't completed yet.
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
    results_data = await container.artifact_store.get(f"jobs/{job_id}/results.json")

    if results_data is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Results not found in artifact store",
        )

    return JobResultsResponse.model_validate_json(results_data)
