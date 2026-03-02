"""Worker management endpoints."""

from __future__ import annotations

from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Query
from pydantic import BaseModel, ConfigDict

router = APIRouter()


class WorkerStatus(str):
    """Worker status enumeration."""

    IDLE = "idle"
    BUSY = "busy"
    OFFLINE = "offline"
    MAINTENANCE = "maintenance"


class WorkerInfo(BaseModel):
    """Information about a worker node."""

    worker_id: str
    hostname: str
    status: str
    backend_type: str
    capabilities: list[str]
    current_job_id: str | None = None
    jobs_completed: int
    jobs_failed: int
    uptime_seconds: float
    last_heartbeat: datetime
    cpu_usage: float
    memory_usage: float

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "worker_id": "worker-01",
                "hostname": "qnode-01.quantum.local",
                "status": "busy",
                "backend_type": "simulator",
                "capabilities": ["qaoa", "vqe", "grover"],
                "current_job_id": "550e8400-e29b-41d4-a716-446655440000",
                "jobs_completed": 1250,
                "jobs_failed": 3,
                "uptime_seconds": 86400.0,
                "last_heartbeat": "2024-01-15T10:30:00Z",
                "cpu_usage": 45.5,
                "memory_usage": 62.3,
            }
        }
    )


class WorkerListResponse(BaseModel):
    """Response with list of workers."""

    workers: list[WorkerInfo]
    total: int
    active: int
    idle: int

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "workers": [
                    {
                        "worker_id": "worker-01",
                        "hostname": "qnode-01.quantum.local",
                        "status": "busy",
                        "backend_type": "simulator",
                        "capabilities": ["qaoa", "vqe", "grover"],
                        "current_job_id": "550e8400-e29b-41d4-a716-446655440000",
                        "jobs_completed": 1250,
                        "jobs_failed": 3,
                        "uptime_seconds": 86400.0,
                        "last_heartbeat": "2024-01-15T10:30:00Z",
                        "cpu_usage": 45.5,
                        "memory_usage": 62.3,
                    }
                ],
                "total": 5,
                "active": 3,
                "idle": 2,
            }
        }
    )


@router.get("", response_model=WorkerListResponse)
async def list_workers(
    status_filter: Annotated[str | None, Query(alias="status")] = None,
    backend_type: Annotated[str | None, Query(alias="backend_type")] = None,
) -> WorkerListResponse:
    """
    List all available worker nodes.

    Supports filtering by status and backend type.
    """
    # In production, this would query the worker registry
    # For now, return mock data
    workers = [
        WorkerInfo(
            worker_id="worker-01",
            hostname="qnode-01.quantum.local",
            status="busy",
            backend_type="simulator",
            capabilities=["qaoa", "vqe", "grover"],
            current_job_id="550e8400-e29b-41d4-a716-446655440000",
            jobs_completed=1250,
            jobs_failed=3,
            uptime_seconds=86400.0,
            last_heartbeat=datetime.utcnow(),
            cpu_usage=45.5,
            memory_usage=62.3,
        ),
        WorkerInfo(
            worker_id="worker-02",
            hostname="qnode-02.quantum.local",
            status="idle",
            backend_type="simulator",
            capabilities=["qaoa", "vqe"],
            current_job_id=None,
            jobs_completed=980,
            jobs_failed=2,
            uptime_seconds=43200.0,
            last_heartbeat=datetime.utcnow(),
            cpu_usage=5.2,
            memory_usage=30.1,
        ),
    ]

    active_count = sum(1 for w in workers if w.status == "busy")
    idle_count = sum(1 for w in workers if w.status == "idle")

    return WorkerListResponse(
        workers=workers,
        total=len(workers),
        active=active_count,
        idle=idle_count,
    )


@router.get("/{worker_id}", response_model=WorkerInfo)
async def get_worker(worker_id: str) -> WorkerInfo:
    """
    Get detailed information about a specific worker.
    """
    # In production, this would query the worker registry
    # For now, return mock data
    return WorkerInfo(
        worker_id=worker_id,
        hostname="qnode-01.quantum.local",
        status="busy",
        backend_type="simulator",
        capabilities=["qaoa", "vqe", "grover"],
        current_job_id="550e8400-e29b-41d4-a716-446655440000",
        jobs_completed=1250,
        jobs_failed=3,
        uptime_seconds=86400.0,
        last_heartbeat=datetime.utcnow(),
        cpu_usage=45.5,
        memory_usage=62.3,
    )


@router.post("/{worker_id}/drain", status_code=204)
async def drain_worker(worker_id: str) -> None:
    """
    Drain a worker node.

    This marks the worker to stop accepting new jobs after current ones complete.
    """
    # In production, this would set the worker to drain mode
    pass


@router.post("/{worker_id}/restart", status_code=204)
async def restart_worker(worker_id: str) -> None:
    """
    Restart a worker node.

    This gracefully restarts the worker, waiting for current jobs to complete.
    """
    # In production, this would gracefully restart the worker
    pass
