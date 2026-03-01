"""Job-related Pydantic schemas."""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class JobStatus(str, Enum):
    """Possible job statuses."""

    PENDING = "pending"
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


from .crypto import CryptoSettings


class JobCreate(BaseModel):
    """Request body for creating a new job."""

    algorithm: str = Field(
        ...,
        description="Name of the optimization algorithm to use",
        examples=["qaoa", "vqe", "grover"],
    )
    backend: str = Field(
        ...,
        description="Quantum backend to execute on",
        examples=["qiskit_aer", "ibm_quantum"],
    )
    parameters: dict[str, Any] = Field(
        default_factory=dict,
        description="Algorithm-specific parameters",
    )
    crypto: CryptoSettings = Field(
        default_factory=CryptoSettings,
        description="Cryptographic settings for the job",
    )
    problem_data: dict[str, Any] = Field(
        ...,
        description="Problem definition data",
    )
    name: str | None = Field(
        None,
        max_length=255,
        description="Optional human-readable job name",
    )
    priority: int = Field(
        default=5,
        ge=1,
        le=10,
        description="Job priority (1=lowest, 10=highest)",
    )
    callback_url: str | None = Field(
        None,
        description="Webhook URL to call when job completes",
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "algorithm": "qaoa",
                "backend": "qiskit_aer",
                "parameters": {"p": 2, "optimizer": "COBYLA"},
                "problem_data": {
                    "type": "maxcut",
                    "graph": {"nodes": 4, "edges": [[0, 1], [1, 2], [2, 3], [3, 0]]},
                },
            }
        }
    )


class JobResponse(BaseModel):
    """Response model for job details."""

    id: UUID
    tenant_id: str
    name: str | None
    algorithm: str
    backend: str
    parameters: dict[str, Any]
    status: JobStatus
    priority: int
    created_at: datetime
    started_at: datetime | None
    completed_at: datetime | None
    error_message: str | None = None
    progress: float | None = Field(None, ge=0, le=100)
    estimated_completion: datetime | None = None

    model_config = ConfigDict(from_attributes=True)


class JobListResponse(BaseModel):
    """Paginated list of jobs."""

    jobs: list[JobResponse]
    total: int
    limit: int
    offset: int

    @property
    def has_more(self) -> bool:
        """Check if there are more results available."""
        return self.offset + len(self.jobs) < self.total


class JobProgress(BaseModel):
    """Job progress update model."""

    job_id: UUID
    status: JobStatus
    progress: float = Field(ge=0, le=100)
    message: str | None = None
    current_iteration: int | None = None
    total_iterations: int | None = None
    timestamp: datetime
