"""
Batch Job Submission API.

Features:
- Submit multiple jobs in a single request
- Batch status tracking
- Parallel execution
- Batch cancellation
- Progress tracking
"""

import asyncio
import logging
import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Any

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from pydantic import BaseModel, Field

from api.routers.auth import get_current_user

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/batch", tags=["Batch Jobs"])


class BatchStatus(str, Enum):
    """Batch job status."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    PARTIAL = "partial"


class JobRequest(BaseModel):
    """Single job request within a batch."""

    job_id: str | None = None
    job_type: str = Field(..., description="Type of job: optimization, simulation, etc.")
    name: str | None = None
    config: dict[str, Any] = Field(default_factory=dict)
    priority: int = Field(default=5, ge=1, le=10)
    depends_on: list[str] = Field(default_factory=list, description="Job IDs this depends on")
    retry_count: int = Field(default=0, ge=0, le=5)


class BatchCreate(BaseModel):
    """Create a batch of jobs."""

    name: str = Field(..., min_length=1, max_length=100)
    description: str | None = None
    jobs: list[JobRequest] = Field(..., min_length=1, max_length=100)
    parallel: bool = Field(default=True, description="Run jobs in parallel")
    max_parallel: int = Field(default=10, ge=1, le=50, description="Max parallel jobs")
    stop_on_failure: bool = Field(default=False)
    notify_on_complete: str | None = Field(None, description="Webhook URL for notification")
    tags: list[str] = Field(default_factory=list)


class BatchJobStatus(BaseModel):
    """Status of a single job in the batch."""

    job_id: str
    job_type: str
    name: str | None
    status: str
    started_at: datetime | None
    completed_at: datetime | None
    result: dict | None
    error: str | None
    progress: float = 0.0


class BatchResponse(BaseModel):
    """Batch creation response."""

    batch_id: str
    name: str
    total_jobs: int
    status: BatchStatus
    created_at: datetime


class BatchStatusResponse(BaseModel):
    """Full batch status response."""

    batch_id: str
    name: str
    description: str | None
    status: BatchStatus
    created_at: datetime
    started_at: datetime | None
    completed_at: datetime | None
    total_jobs: int
    completed_jobs: int
    failed_jobs: int
    pending_jobs: int
    running_jobs: int
    progress: float
    jobs: list[BatchJobStatus]
    duration_seconds: float | None


class BatchList(BaseModel):
    """List of batches."""

    batches: list[BatchStatusResponse]
    total: int


_batches: dict[str, dict] = {}


async def execute_single_job(job: dict, batch_id: str) -> dict:
    """Execute a single job within a batch."""
    job_id = job.get("job_id")
    job_type = job.get("job_type")
    config = job.get("config", {})

    started_at = datetime.now(timezone.utc)

    job_status = {
        "job_id": job_id,
        "job_type": job_type,
        "name": job.get("name"),
        "status": "running",
        "started_at": started_at.isoformat(),
        "completed_at": None,
        "result": None,
        "error": None,
        "progress": 0.0,
    }

    try:
        if job_type == "optimization":
            from api.routers.jobs import submit_optimization_job

            result = await submit_optimization_job(
                user_id=f"batch_{batch_id}",
                problem_data=config.get("problem_data", {}),
                backend=config.get("backend", "simulator"),
                options=config.get("options"),
            )
            job_status["result"] = result
            job_status["status"] = "completed"

        elif job_type == "simulation":
            await asyncio.sleep(0.5)
            job_status["result"] = {"simulated": True, "config": config}
            job_status["status"] = "completed"

        elif job_type == "analysis":
            await asyncio.sleep(0.3)
            job_status["result"] = {"analyzed": True, "config": config}
            job_status["status"] = "completed"

        else:
            job_status["status"] = "failed"
            job_status["error"] = f"Unknown job type: {job_type}"

    except Exception as e:
        logger.error(f"Job {job_id} failed: {e}")
        job_status["status"] = "failed"
        job_status["error"] = str(e)

    completed_at = datetime.now(timezone.utc)
    job_status["completed_at"] = completed_at.isoformat()

    return job_status


async def execute_batch(batch_id: str):
    """Execute all jobs in a batch."""
    batch = _batches.get(batch_id)
    if not batch:
        return

    batch["status"] = BatchStatus.RUNNING.value
    batch["started_at"] = datetime.now(timezone.utc).isoformat()

    jobs = batch.get("jobs", [])
    parallel = batch.get("parallel", True)
    max_parallel = batch.get("max_parallel", 10)
    stop_on_failure = batch.get("stop_on_failure", False)

    dependency_graph: dict[str, list[str]] = {}
    for job in jobs:
        job_id = job.get("job_id")
        depends_on = job.get("depends_on", [])
        dependency_graph[job_id] = depends_on

    completed_job_ids: set[str] = set()
    running_jobs: dict[str, asyncio.Task] = {}

    while len(completed_job_ids) < len(jobs) and batch.get("status") != BatchStatus.CANCELLED.value:
        ready_jobs = []
        for job in jobs:
            job_id = job.get("job_id")
            if job_id in completed_job_ids:
                continue
            if job_id in running_jobs:
                continue

            dependencies = dependency_graph.get(job_id, [])
            if all(dep in completed_job_ids for dep in dependencies):
                ready_jobs.append(job)

        ready_jobs.sort(key=lambda j: j.get("priority", 5), reverse=True)

        slots_available = max_parallel - len(running_jobs)
        jobs_to_start = ready_jobs[:slots_available]

        for job in jobs_to_start:
            job_id = job.get("job_id")
            task = asyncio.create_task(execute_single_job(job, batch_id))
            running_jobs[job_id] = task

        if not running_jobs:
            break

        done, _ = await asyncio.wait(
            running_jobs.values(),
            return_when=asyncio.FIRST_COMPLETED,
            timeout=1.0,
        )

        for task in done:
            for job_id, t in list(running_jobs.items()):
                if t == task:
                    try:
                        result = task.result()
                        batch["job_results"][job_id] = result
                        completed_job_ids.add(job_id)

                        if result.get("status") == "failed" and stop_on_failure:
                            batch["status"] = BatchStatus.FAILED.value
                            batch["completed_at"] = datetime.now(timezone.utc).isoformat()
                            logger.warning(f"Batch {batch_id} stopped due to failure")
                            return
                    except Exception as e:
                        logger.error(f"Job {job_id} task error: {e}")
                        batch["job_results"][job_id] = {
                            "job_id": job_id,
                            "status": "failed",
                            "error": str(e),
                        }
                        completed_job_ids.add(job_id)

                    del running_jobs[job_id]
                    break

    failed_count = sum(1 for r in batch["job_results"].values() if r.get("status") == "failed")
    completed_count = sum(
        1 for r in batch["job_results"].values() if r.get("status") == "completed"
    )

    if batch.get("status") == BatchStatus.CANCELLED.value:
        pass
    elif failed_count == len(jobs):
        batch["status"] = BatchStatus.FAILED.value
    elif failed_count > 0:
        batch["status"] = BatchStatus.PARTIAL.value
    else:
        batch["status"] = BatchStatus.COMPLETED.value

    batch["completed_at"] = datetime.now(timezone.utc).isoformat()

    notify_url = batch.get("notify_on_complete")
    if notify_url:
        try:
            import httpx

            async with httpx.AsyncClient() as client:
                await client.post(
                    notify_url,
                    json={
                        "batch_id": batch_id,
                        "status": batch["status"],
                        "completed_jobs": completed_count,
                        "failed_jobs": failed_count,
                    },
                )
        except Exception as e:
            logger.warning(f"Failed to notify webhook: {e}")

    logger.info(f"Batch {batch_id} completed: {batch['status']}")


@router.post("/", response_model=BatchResponse, status_code=201)
async def create_batch(
    batch_create: BatchCreate,
    background_tasks: BackgroundTasks,
    current_user: dict = Depends(get_current_user),
):
    """Create and submit a batch of jobs."""
    batch_id = f"batch_{uuid.uuid4().hex[:12]}"
    now = datetime.now(timezone.utc)
    user_id = current_user.get("sub", "anonymous")

    # Validate webhook URL if provided
    if batch_create.notify_on_complete:
        from api.security.ssrf_protection import validate_webhook_url

        is_valid, error = validate_webhook_url(batch_create.notify_on_complete)
        if not is_valid:
            raise HTTPException(status_code=400, detail=f"notify_on_complete URL rejected: {error}")

    jobs = []
    job_results = {}
    for i, job_req in enumerate(batch_create.jobs):
        job_id = job_req.job_id or f"{batch_id}_job_{i + 1}"
        job_data = {
            "job_id": job_id,
            "job_type": job_req.job_type,
            "name": job_req.name,
            "config": job_req.config,
            "priority": job_req.priority,
            "depends_on": job_req.depends_on,
            "retry_count": job_req.retry_count,
        }
        jobs.append(job_data)
        job_results[job_id] = {
            "job_id": job_id,
            "job_type": job_req.job_type,
            "name": job_req.name,
            "status": "pending",
            "started_at": None,
            "completed_at": None,
            "result": None,
            "error": None,
            "progress": 0.0,
        }

    batch_data = {
        "batch_id": batch_id,
        "name": batch_create.name,
        "description": batch_create.description,
        "status": BatchStatus.PENDING.value,
        "created_at": now.isoformat(),
        "started_at": None,
        "completed_at": None,
        "user_id": user_id,
        "jobs": jobs,
        "job_results": job_results,
        "parallel": batch_create.parallel,
        "max_parallel": batch_create.max_parallel,
        "stop_on_failure": batch_create.stop_on_failure,
        "notify_on_complete": batch_create.notify_on_complete,
        "tags": batch_create.tags,
    }

    _batches[batch_id] = batch_data

    background_tasks.add_task(execute_batch, batch_id)

    logger.info(f"Created batch: {batch_id} with {len(jobs)} jobs by user: {user_id}")

    return BatchResponse(
        batch_id=batch_id,
        name=batch_create.name,
        total_jobs=len(jobs),
        status=BatchStatus.PENDING,
        created_at=now,
    )


@router.get("/", response_model=BatchList)
async def list_batches(
    skip: int = 0,
    limit: int = 50,
    status_filter: BatchStatus | None = None,
    current_user: dict = Depends(get_current_user),
):
    """List all batches for the current user."""
    user_id = current_user.get("sub")
    batches = []
    for batch in _batches.values():
        if batch.get("user_id") != user_id:
            continue
        if status_filter and batch.get("status") != status_filter.value:
            continue

        batches.append(_format_batch_status(batch))

    return BatchList(batches=batches[skip : skip + limit], total=len(batches))


def _check_batch_ownership(batch: dict, user_id: str) -> None:
    """Check if user owns the batch."""
    if batch.get("user_id") != user_id:
        raise HTTPException(status_code=403, detail="Access denied")


@router.get("/{batch_id}", response_model=BatchStatusResponse)
async def get_batch_status(
    batch_id: str,
    current_user: dict = Depends(get_current_user),
):
    """Get detailed batch status."""
    batch = _batches.get(batch_id)
    if not batch:
        raise HTTPException(status_code=404, detail="Batch not found")

    _check_batch_ownership(batch, current_user.get("sub"))

    return _format_batch_status(batch)


def _format_batch_status(batch: dict) -> BatchStatusResponse:
    """Format batch status response."""
    job_results = batch.get("job_results", {})

    completed = sum(1 for j in job_results.values() if j.get("status") == "completed")
    failed = sum(1 for j in job_results.values() if j.get("status") == "failed")
    pending = sum(1 for j in job_results.values() if j.get("status") == "pending")
    running = sum(1 for j in job_results.values() if j.get("status") == "running")
    total = len(job_results)

    started_at = batch.get("started_at")
    completed_at = batch.get("completed_at")
    created_at = batch.get("created_at")

    duration = None
    if started_at and completed_at:
        start = datetime.fromisoformat(started_at)
        end = datetime.fromisoformat(completed_at)
        duration = (end - start).total_seconds()

    jobs_status = []
    for job_data in job_results.values():
        jobs_status.append(
            BatchJobStatus(
                job_id=job_data.get("job_id"),
                job_type=job_data.get("job_type"),
                name=job_data.get("name"),
                status=job_data.get("status", "pending"),
                started_at=datetime.fromisoformat(job_data["started_at"])
                if job_data.get("started_at")
                else None,
                completed_at=datetime.fromisoformat(job_data["completed_at"])
                if job_data.get("completed_at")
                else None,
                result=job_data.get("result"),
                error=job_data.get("error"),
                progress=job_data.get("progress", 0.0),
            )
        )

    return BatchStatusResponse(
        batch_id=batch["batch_id"],
        name=batch["name"],
        description=batch.get("description"),
        status=BatchStatus(batch["status"]),
        created_at=datetime.fromisoformat(created_at) if created_at else None,
        started_at=datetime.fromisoformat(started_at) if started_at else None,
        completed_at=datetime.fromisoformat(completed_at) if completed_at else None,
        total_jobs=total,
        completed_jobs=completed,
        failed_jobs=failed,
        pending_jobs=pending,
        running_jobs=running,
        progress=completed / max(total, 1),
        jobs=jobs_status,
        duration_seconds=duration,
    )


@router.post("/{batch_id}/cancel")
async def cancel_batch(
    batch_id: str,
    current_user: dict = Depends(get_current_user),
):
    """Cancel a running batch."""
    batch = _batches.get(batch_id)
    if not batch:
        raise HTTPException(status_code=404, detail="Batch not found")

    _check_batch_ownership(batch, current_user.get("sub", ""))

    if batch["status"] in [
        BatchStatus.COMPLETED.value,
        BatchStatus.FAILED.value,
        BatchStatus.CANCELLED.value,
    ]:
        raise HTTPException(status_code=400, detail=f"Batch already {batch['status']}")

    batch["status"] = BatchStatus.CANCELLED.value
    batch["completed_at"] = datetime.now(timezone.utc).isoformat()

    for job_id, job in batch.get("job_results", {}).items():
        if job.get("status") in ["pending", "running"]:
            job["status"] = "cancelled"
            job["error"] = "Batch cancelled"

    logger.info(f"Batch {batch_id} cancelled by user: {current_user.get('sub')}")

    return {"message": "Batch cancelled", "batch_id": batch_id}


@router.post("/{batch_id}/retry")
async def retry_batch(
    batch_id: str,
    background_tasks: BackgroundTasks,
    failed_only: bool = True,
    current_user: dict = Depends(get_current_user),
):
    """Retry failed jobs in a batch."""
    batch = _batches.get(batch_id)
    if not batch:
        raise HTTPException(status_code=404, detail="Batch not found")

    _check_batch_ownership(batch, current_user.get("sub", ""))

    if batch["status"] not in [
        BatchStatus.FAILED.value,
        BatchStatus.PARTIAL.value,
        BatchStatus.CANCELLED.value,
    ]:
        raise HTTPException(status_code=400, detail="Batch cannot be retried")

    for job_id, job in batch.get("job_results", {}).items():
        if failed_only and job.get("status") not in ["failed", "cancelled"]:
            continue
        job["status"] = "pending"
        job["started_at"] = None
        job["completed_at"] = None
        job["result"] = None
        job["error"] = None
        job["progress"] = 0.0

    batch["status"] = BatchStatus.PENDING.value
    batch["started_at"] = None
    batch["completed_at"] = None

    background_tasks.add_task(execute_batch, batch_id)

    return {"message": "Batch retry started", "batch_id": batch_id}


@router.delete("/{batch_id}")
async def delete_batch(
    batch_id: str,
    current_user: dict = Depends(get_current_user),
):
    """Delete a batch and its results."""
    batch = _batches.get(batch_id)
    if not batch:
        raise HTTPException(status_code=404, detail="Batch not found")

    _check_batch_ownership(batch, current_user.get("sub", ""))

    if batch["status"] == BatchStatus.RUNNING.value:
        raise HTTPException(status_code=400, detail="Cannot delete running batch. Cancel first.")

    del _batches[batch_id]

    logger.info(f"Batch {batch_id} deleted by user: {current_user.get('sub')}")

    return {"message": "Batch deleted", "batch_id": batch_id}


@router.get("/{batch_id}/results")
async def get_batch_results(
    batch_id: str,
    current_user: dict = Depends(get_current_user),
):
    """Get all results from a completed batch."""
    batch = _batches.get(batch_id)
    if not batch:
        raise HTTPException(status_code=404, detail="Batch not found")

    _check_batch_ownership(batch, current_user.get("sub", ""))

    results = []
    for job_id, job in batch.get("job_results", {}).items():
        if job.get("status") == "completed" and job.get("result"):
            results.append(
                {
                    "job_id": job_id,
                    "job_type": job.get("job_type"),
                    "result": job.get("result"),
                }
            )

    return {
        "batch_id": batch_id,
        "results": results,
        "total": len(results),
    }


@router.post("/{batch_id}/export")
async def export_batch_results(
    batch_id: str,
    format: str = "json",
    current_user: dict = Depends(get_current_user),
):
    """Export batch results in specified format."""
    batch = _batches.get(batch_id)
    if not batch:
        raise HTTPException(status_code=404, detail="Batch not found")

    _check_batch_ownership(batch, current_user.get("sub", ""))

    results = []
    for job_id, job in batch.get("job_results", {}).items():
        results.append(
            {
                "job_id": job_id,
                "job_type": job.get("job_type"),
                "status": job.get("status"),
                "result": job.get("result"),
                "error": job.get("error"),
            }
        )

    if format == "json":
        return {"format": "json", "data": results}
    elif format == "csv":
        import csv
        import io

        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(["job_id", "job_type", "status", "result", "error"])
        for r in results:
            writer.writerow(
                [
                    r["job_id"],
                    r["job_type"],
                    r["status"],
                    json.dumps(r.get("result")) if r.get("result") else "",
                    r.get("error") or "",
                ]
            )
        return {"format": "csv", "data": output.getvalue()}
    else:
        raise HTTPException(status_code=400, detail=f"Unsupported format: {format}")


import json
