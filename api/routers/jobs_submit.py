"""
Job submission endpoints.

Handles creation and submission of quantum optimization jobs.
Split from jobs.py for maintainability.
"""

import logging
import os
import uuid
from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, Field

from api.security.rate_limiter import RateLimits, limiter

logger = logging.getLogger(__name__)
router = APIRouter()
security = HTTPBearer()

DEMO_MODE = os.getenv("DEMO_MODE", "false").lower() == "true"


class JobSubmitRequest(BaseModel):
    """Job submission request."""

    problem_type: str = Field(..., description="Type: QAOA, VQE, or ANNEALING")
    problem_config: dict[str, Any] = Field(..., description="Problem-specific configuration")
    parameters: dict[str, Any] | None = Field(default=None, description="Optimization parameters")
    webhook_url: str | None = Field(default=None, description="Callback URL for notifications")
    encrypt_results: bool = Field(default=False, description="Encrypt results with user's KEM key")


class JobSubmitResponse(BaseModel):
    """Job submission response."""

    job_id: str
    status: str
    message: str
    created_at: datetime


@router.post("", response_model=JobSubmitResponse)
@limiter.limit(RateLimits.JOB_SUBMIT)
async def submit_job(
    request: Request,
    job_data: JobSubmitRequest,
    background_tasks: BackgroundTasks,
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
) -> JobSubmitResponse:
    """
    Submit a new optimization job.

    Supports QAOA, VQE, and quantum annealing problems.
    Results can be encrypted with user's ML-KEM public key.
    """
    job_id = str(uuid.uuid4())

    user_id = None
    if credentials and not DEMO_MODE:
        user_id = getattr(request.state, "user_id", None)
        if not user_id:
            raise HTTPException(status_code=401, detail="Authentication required")

    job_record = {
        "id": job_id,
        "user_id": user_id,
        "problem_type": job_data.problem_type.upper(),
        "problem_config": job_data.problem_config,
        "parameters": job_data.parameters or {},
        "status": "pending",
        "created_at": datetime.now(UTC).isoformat(),
        "webhook_url": job_data.webhook_url,
        "encrypt_results": job_data.encrypt_results,
    }

    from api.routers.jobs import _jobs_db, process_optimization_job

    _jobs_db[job_id] = job_record

    background_tasks.add_task(process_optimization_job, job_id)

    logger.info(f"Job submitted: {job_id} type={job_data.problem_type} user={user_id}")

    return JobSubmitResponse(
        job_id=job_id,
        status="pending",
        message="Job submitted successfully",
        created_at=datetime.now(UTC),
    )
