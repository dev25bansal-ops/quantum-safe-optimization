"""Job management endpoints."""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status

from qsop.api.deps import CurrentTenant, ServiceContainerDep
from qsop.api.schemas.error import NotFoundErrorDetail
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

    **Example - QAOA MaxCut:**
    ```json
    {
        "algorithm": "qaoa",
        "backend": "qiskit_aer",
        "parameters": {"p": 2, "optimizer": "COBYLA", "max_iterations": 100},
        "problem_config": {
            "type": "qaoa_maxcut",
            "graph": {"nodes": 4, "edges": [[0, 1], [1, 2], [2, 3], [3, 0], [0, 2]]},
            "weighted": false
        },
        "name": "MaxCut-4Nodes-Trial1",
        "priority": 5
    }
    ```

    **Example - VQE Molecular Hamiltonian:**
    ```json
    {
        "algorithm": "vqe",
        "backend": "qiskit_aer",
        "parameters": {"ansatz": "UCCSD", "optimizer": "SPSA", "max_iterations": 200},
        "problem_config": {
            "type": "vqe_molecular_hamiltonian",
            "molecule": "H2",
            "basis": "sto-3g",
            "geometry": [[0.0, 0.0, 0.0], [0.0, 0.0, 0.735]],
            "charge": 0,
            "spin": 0
        },
        "name": "H2-VQE-Energy-Calc",
        "priority": 8
    }
    ```
    """
    try:
        job = await container.job_repo.create(
            tenant_id=tenant_id,
            algorithm=job_data.algorithm,
            backend=job_data.backend,
            parameters=job_data.parameters,
            problem_data=job_data.problem_config.model_dump(),
            name=job_data.name,
            priority=job_data.priority,
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

    **Query Parameters:**
    - `status`: Filter by job status (pending, queued, running, completed, failed, cancelled)
    - `limit`: Maximum number of results to return (default: 20, max: 100)
    - `offset`: Number of results to skip (default: 0)

    **Example:**
    ```
    GET /jobs?status=completed&limit=10&offset=0
    ```
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


@router.get("/{job_id}", response_model=JobResponse | JobResultsResponse)
async def get_job(
    job_id: UUID,
    tenant_id: CurrentTenant,
    container: ServiceContainerDep,
    include_results: Annotated[
        bool, Query(alias="include_results", description="Include results for completed jobs")
    ] = False,
) -> JobResponse | JobResultsResponse:
    """
    Get details of a specific job.

    For completed jobs, set `include_results=true` to automatically include
    the results in the response.

    **Example:**
    ```
    GET /jobs/550e8400-e29b-41d4-a716-446655440000?include_results=true
    ```
    """
    job = await container.job_repo.get_by_id(job_id, tenant_id)

    if job is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Job {job_id} not found",
        )

    # For completed jobs with include_results, fetch results
    # Implementation depends on artifact store interface
    if include_results and job.status == JobStatus.COMPLETED:
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail="Result retrieval not yet implemented via this endpoint. Use GET /jobs/{job_id}/results instead.",
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

    **Example:**
    ```
    DELETE /jobs/550e8400-e29b-41d4-a716-446655440000
    ```
    """
    job = await container.job_repo.get_by_id(job_id, tenant_id)

    if job is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Job {job_id} not found",
        )

    if job.status in (JobStatus.COMPLETED, JobStatus.FAILED, JobStatus.CANCELLED):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot cancel job with status '{job.status.value}'",
        )

    await container.job_repo.update_status(job_id, JobStatus.CANCELLED.value)
