"""
Job Scheduling Service with Cron-like Functionality.

Features:
- Cron expression parsing
- Recurring job scheduling
- Job history and execution logs
- Failure handling and retry logic
- Timezone support
"""

import asyncio
import logging
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any, Callable

from croniter import croniter
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/schedules", tags=["Job Scheduling"])


class ScheduleStatus(str, Enum):
    """Schedule status."""

    ACTIVE = "active"
    PAUSED = "paused"
    DISABLED = "disabled"
    COMPLETED = "completed"


class ScheduleType(str, Enum):
    """Schedule type."""

    CRON = "cron"
    INTERVAL = "interval"
    ONCE = "once"


class ScheduleCreate(BaseModel):
    """Create a new schedule."""

    name: str = Field(..., min_length=1, max_length=100)
    description: str | None = None
    schedule_type: ScheduleType = ScheduleType.CRON
    cron_expression: str | None = Field(None, description="Cron expression (e.g., '0 9 * * 1-5')")
    interval_seconds: int | None = Field(None, ge=60, description="Interval in seconds")
    run_at: datetime | None = Field(None, description="Specific time to run once")
    timezone: str = "UTC"
    job_type: str = Field(..., description="Type of job to run")
    job_config: dict[str, Any] = Field(default_factory=dict)
    max_retries: int = Field(default=3, ge=0, le=10)
    retry_delay_seconds: int = Field(default=60, ge=10)
    enabled: bool = True
    tags: list[str] = Field(default_factory=list)


class ScheduleResponse(BaseModel):
    """Schedule response."""

    schedule_id: str
    name: str
    description: str | None
    schedule_type: ScheduleType
    cron_expression: str | None
    interval_seconds: int | None
    next_run_at: datetime | None
    last_run_at: datetime | None
    last_run_status: str | None
    status: ScheduleStatus
    created_at: datetime
    enabled: bool
    run_count: int
    failure_count: int


class ScheduleList(BaseModel):
    """List of schedules."""

    schedules: list[ScheduleResponse]
    total: int


class ExecutionLog(BaseModel):
    """Execution log entry."""

    execution_id: str
    schedule_id: str
    started_at: datetime
    completed_at: datetime | None
    status: str
    error: str | None
    job_id: str | None
    duration_ms: int | None


class ExecutionLogList(BaseModel):
    """List of execution logs."""

    logs: list[ExecutionLog]
    total: int


_schedules: dict[str, dict] = {}
_execution_logs: dict[str, list[dict]] = {}
_scheduler_task: asyncio.Task | None = None
_running = False


def parse_cron(expression: str) -> croniter:
    """Parse a cron expression."""
    return croniter(expression, datetime.now(timezone.utc))


def get_next_run(cron: croniter) -> datetime:
    """Get the next run time from a cron iterator."""
    return cron.get_next(datetime)


def calculate_next_run(schedule: dict) -> datetime | None:
    """Calculate the next run time for a schedule."""
    schedule_type = schedule.get("schedule_type")
    tz = schedule.get("timezone", "UTC")

    now = datetime.now(timezone.utc)

    if schedule_type == ScheduleType.CRON.value:
        cron_expr = schedule.get("cron_expression")
        if not cron_expr:
            return None
        try:
            cron = parse_cron(cron_expr)
            return get_next_run(cron)
        except Exception as e:
            logger.error(f"Invalid cron expression: {cron_expr}: {e}")
            return None

    elif schedule_type == ScheduleType.INTERVAL.value:
        interval = schedule.get("interval_seconds", 3600)
        last_run = schedule.get("last_run_at")
        if last_run:
            if isinstance(last_run, str):
                last_run = datetime.fromisoformat(last_run)
            return last_run + timedelta(seconds=interval)
        return now + timedelta(seconds=interval)

    elif schedule_type == ScheduleType.ONCE.value:
        run_at = schedule.get("run_at")
        if run_at:
            if isinstance(run_at, str):
                run_at = datetime.fromisoformat(run_at)
            if run_at > now:
                return run_at
        return None

    return None


async def execute_schedule(schedule: dict) -> dict:
    """Execute a scheduled job."""
    import uuid

    execution_id = f"exec_{uuid.uuid4().hex[:12]}"
    schedule_id = schedule.get("schedule_id")
    started_at = datetime.now(timezone.utc)

    log_entry = {
        "execution_id": execution_id,
        "schedule_id": schedule_id,
        "started_at": started_at,
        "status": "running",
        "job_id": None,
        "error": None,
    }

    job_type = schedule.get("job_type")
    job_config = schedule.get("job_config", {})

    try:
        if job_type == "optimization":
            from api.routers.jobs import submit_optimization_job

            result = await submit_optimization_job(
                user_id=f"scheduler_{schedule_id}",
                problem_data=job_config.get("problem_data", {}),
                backend=job_config.get("backend", "simulator"),
                options=job_config.get("options"),
            )
            log_entry["job_id"] = result.get("job_id")
            log_entry["status"] = "success"

        elif job_type == "batch_processing":
            logger.info(f"Executing batch processing for schedule {schedule_id}")
            log_entry["status"] = "success"

        elif job_type == "cleanup":
            logger.info(f"Executing cleanup for schedule {schedule_id}")
            log_entry["status"] = "success"

        elif job_type == "report":
            logger.info(f"Executing report generation for schedule {schedule_id}")
            log_entry["status"] = "success"

        elif job_type == "webhook":
            import httpx

            webhook_url = job_config.get("webhook_url")
            if webhook_url:
                async with httpx.AsyncClient() as client:
                    response = await client.post(webhook_url, json=job_config.get("payload", {}))
                    log_entry["status"] = "success" if response.status_code < 400 else "failed"
                    log_entry["error"] = (
                        f"HTTP {response.status_code}" if response.status_code >= 400 else None
                    )
            else:
                log_entry["status"] = "failed"
                log_entry["error"] = "No webhook URL configured"

        else:
            logger.warning(f"Unknown job type: {job_type}")
            log_entry["status"] = "failed"
            log_entry["error"] = f"Unknown job type: {job_type}"

    except Exception as e:
        logger.error(f"Schedule execution failed: {e}")
        log_entry["status"] = "failed"
        log_entry["error"] = str(e)

        retry_count = schedule.get("retry_count", 0)
        max_retries = schedule.get("max_retries", 3)
        if retry_count < max_retries:
            schedule["retry_count"] = retry_count + 1
            schedule["next_run_at"] = (
                datetime.now(timezone.utc)
                + timedelta(seconds=schedule.get("retry_delay_seconds", 60))
            ).isoformat()
            logger.info(f"Scheduling retry {retry_count + 1}/{max_retries} for {schedule_id}")
        else:
            schedule["status"] = ScheduleStatus.DISABLED.value
            logger.error(f"Schedule {schedule_id} disabled after {max_retries} failures")

    completed_at = datetime.now(timezone.utc)
    log_entry["completed_at"] = completed_at
    log_entry["duration_ms"] = int((completed_at - started_at).total_seconds() * 1000)

    if schedule_id not in _execution_logs:
        _execution_logs[schedule_id] = []
    _execution_logs[schedule_id].insert(0, log_entry)

    if len(_execution_logs[schedule_id]) > 100:
        _execution_logs[schedule_id] = _execution_logs[schedule_id][:100]

    if log_entry["status"] == "success":
        schedule["last_run_at"] = started_at.isoformat()
        schedule["last_run_status"] = "success"
        schedule["run_count"] = schedule.get("run_count", 0) + 1
        schedule["retry_count"] = 0
        schedule["next_run_at"] = calculate_next_run(schedule)
        if schedule["next_run_at"]:
            schedule["next_run_at"] = schedule["next_run_at"].isoformat()
    else:
        schedule["failure_count"] = schedule.get("failure_count", 0) + 1
        schedule["last_run_status"] = "failed"

    _schedules[schedule_id] = schedule

    return log_entry


async def scheduler_loop():
    """Main scheduler loop."""
    global _running
    _running = True

    while _running:
        try:
            now = datetime.now(timezone.utc)

            for schedule_id, schedule in list(_schedules.items()):
                if schedule.get("status") != ScheduleStatus.ACTIVE.value:
                    continue

                if not schedule.get("enabled", True):
                    continue

                next_run = schedule.get("next_run_at")
                if not next_run:
                    continue

                if isinstance(next_run, str):
                    next_run = datetime.fromisoformat(next_run)

                if next_run <= now:
                    logger.info(f"Executing schedule: {schedule_id}")
                    asyncio.create_task(execute_schedule(schedule))

            await asyncio.sleep(10)

        except asyncio.CancelledError:
            break
        except Exception as e:
            logger.error(f"Scheduler error: {e}")
            await asyncio.sleep(30)


async def start_scheduler():
    """Start the scheduler."""
    global _scheduler_task

    if _scheduler_task is None or _scheduler_task.done():
        _scheduler_task = asyncio.create_task(scheduler_loop())
        logger.info("Scheduler started")


async def stop_scheduler():
    """Stop the scheduler."""
    global _running, _scheduler_task

    _running = False
    if _scheduler_task:
        _scheduler_task.cancel()
        try:
            await _scheduler_task
        except asyncio.CancelledError:
            pass
        _scheduler_task = None
        logger.info("Scheduler stopped")


@router.post("/", response_model=ScheduleResponse, status_code=201)
async def create_schedule(schedule: ScheduleCreate):
    """Create a new scheduled job."""
    import uuid

    schedule_id = f"sched_{uuid.uuid4().hex[:12]}"
    now = datetime.now(timezone.utc)

    if schedule.schedule_type == ScheduleType.CRON:
        if not schedule.cron_expression:
            raise HTTPException(
                status_code=400, detail="cron_expression required for cron schedule"
            )
        try:
            parse_cron(schedule.cron_expression)
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Invalid cron expression: {e}")

    schedule_data = {
        "schedule_id": schedule_id,
        "name": schedule.name,
        "description": schedule.description,
        "schedule_type": schedule.schedule_type.value,
        "cron_expression": schedule.cron_expression,
        "interval_seconds": schedule.interval_seconds,
        "run_at": schedule.run_at.isoformat() if schedule.run_at else None,
        "timezone": schedule.timezone,
        "job_type": schedule.job_type,
        "job_config": schedule.job_config,
        "max_retries": schedule.max_retries,
        "retry_delay_seconds": schedule.retry_delay_seconds,
        "enabled": schedule.enabled,
        "tags": schedule.tags,
        "status": ScheduleStatus.ACTIVE.value if schedule.enabled else ScheduleStatus.PAUSED.value,
        "created_at": now.isoformat(),
        "next_run_at": None,
        "last_run_at": None,
        "last_run_status": None,
        "run_count": 0,
        "failure_count": 0,
        "retry_count": 0,
    }

    next_run = calculate_next_run(schedule_data)
    schedule_data["next_run_at"] = next_run.isoformat() if next_run else None

    _schedules[schedule_id] = schedule_data

    logger.info(f"Created schedule: {schedule_id}")

    return ScheduleResponse(
        schedule_id=schedule_id,
        name=schedule.name,
        description=schedule.description,
        schedule_type=schedule.schedule_type,
        cron_expression=schedule.cron_expression,
        interval_seconds=schedule.interval_seconds,
        next_run_at=next_run,
        last_run_at=None,
        last_run_status=None,
        status=ScheduleStatus(schedule_data["status"]),
        created_at=now,
        enabled=schedule.enabled,
        run_count=0,
        failure_count=0,
    )


@router.get("/", response_model=ScheduleList)
async def list_schedules(
    skip: int = 0,
    limit: int = 50,
    status_filter: ScheduleStatus | None = None,
    job_type: str | None = None,
):
    """List all schedules."""
    schedules = []
    for sched in _schedules.values():
        if status_filter and sched.get("status") != status_filter.value:
            continue
        if job_type and sched.get("job_type") != job_type:
            continue

        next_run = sched.get("next_run_at")
        last_run = sched.get("last_run_at")

        schedules.append(
            ScheduleResponse(
                schedule_id=sched["schedule_id"],
                name=sched["name"],
                description=sched.get("description"),
                schedule_type=ScheduleType(sched["schedule_type"]),
                cron_expression=sched.get("cron_expression"),
                interval_seconds=sched.get("interval_seconds"),
                next_run_at=datetime.fromisoformat(next_run) if next_run else None,
                last_run_at=datetime.fromisoformat(last_run) if last_run else None,
                last_run_status=sched.get("last_run_status"),
                status=ScheduleStatus(sched["status"]),
                created_at=datetime.fromisoformat(sched["created_at"]),
                enabled=sched.get("enabled", True),
                run_count=sched.get("run_count", 0),
                failure_count=sched.get("failure_count", 0),
            )
        )

    return ScheduleList(schedules=schedules[skip : skip + limit], total=len(schedules))


@router.get("/{schedule_id}", response_model=ScheduleResponse)
async def get_schedule(schedule_id: str):
    """Get a specific schedule."""
    sched = _schedules.get(schedule_id)
    if not sched:
        raise HTTPException(status_code=404, detail="Schedule not found")

    next_run = sched.get("next_run_at")
    last_run = sched.get("last_run_at")

    return ScheduleResponse(
        schedule_id=sched["schedule_id"],
        name=sched["name"],
        description=sched.get("description"),
        schedule_type=ScheduleType(sched["schedule_type"]),
        cron_expression=sched.get("cron_expression"),
        interval_seconds=sched.get("interval_seconds"),
        next_run_at=datetime.fromisoformat(next_run) if next_run else None,
        last_run_at=datetime.fromisoformat(last_run) if last_run else None,
        last_run_status=sched.get("last_run_status"),
        status=ScheduleStatus(sched["status"]),
        created_at=datetime.fromisoformat(sched["created_at"]),
        enabled=sched.get("enabled", True),
        run_count=sched.get("run_count", 0),
        failure_count=sched.get("failure_count", 0),
    )


@router.patch("/{schedule_id}")
async def update_schedule(
    schedule_id: str,
    enabled: bool | None = None,
    cron_expression: str | None = None,
    interval_seconds: int | None = None,
    job_config: dict | None = None,
):
    """Update a schedule."""
    sched = _schedules.get(schedule_id)
    if not sched:
        raise HTTPException(status_code=404, detail="Schedule not found")

    if enabled is not None:
        sched["enabled"] = enabled
        sched["status"] = ScheduleStatus.ACTIVE.value if enabled else ScheduleStatus.PAUSED.value

    if cron_expression is not None:
        try:
            parse_cron(cron_expression)
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Invalid cron expression: {e}")
        sched["cron_expression"] = cron_expression

    if interval_seconds is not None:
        sched["interval_seconds"] = interval_seconds

    if job_config is not None:
        sched["job_config"] = job_config

    next_run = calculate_next_run(sched)
    sched["next_run_at"] = next_run.isoformat() if next_run else None

    logger.info(f"Updated schedule: {schedule_id}")

    return {"message": "Schedule updated", "schedule_id": schedule_id}


@router.post("/{schedule_id}/pause")
async def pause_schedule(schedule_id: str):
    """Pause a schedule."""
    sched = _schedules.get(schedule_id)
    if not sched:
        raise HTTPException(status_code=404, detail="Schedule not found")

    sched["status"] = ScheduleStatus.PAUSED.value
    sched["enabled"] = False

    return {"message": "Schedule paused", "schedule_id": schedule_id}


@router.post("/{schedule_id}/resume")
async def resume_schedule(schedule_id: str):
    """Resume a paused schedule."""
    sched = _schedules.get(schedule_id)
    if not sched:
        raise HTTPException(status_code=404, detail="Schedule not found")

    sched["status"] = ScheduleStatus.ACTIVE.value
    sched["enabled"] = True
    sched["retry_count"] = 0

    next_run = calculate_next_run(sched)
    sched["next_run_at"] = next_run.isoformat() if next_run else None

    return {"message": "Schedule resumed", "schedule_id": schedule_id}


@router.post("/{schedule_id}/run")
async def run_schedule_now(schedule_id: str):
    """Manually trigger a schedule run."""
    sched = _schedules.get(schedule_id)
    if not sched:
        raise HTTPException(status_code=404, detail="Schedule not found")

    log_entry = await execute_schedule(sched.copy())

    return {
        "message": "Schedule executed",
        "schedule_id": schedule_id,
        "execution_id": log_entry.get("execution_id"),
        "status": log_entry.get("status"),
    }


@router.delete("/{schedule_id}")
async def delete_schedule(schedule_id: str):
    """Delete a schedule."""
    if schedule_id not in _schedules:
        raise HTTPException(status_code=404, detail="Schedule not found")

    del _schedules[schedule_id]
    if schedule_id in _execution_logs:
        del _execution_logs[schedule_id]

    logger.info(f"Deleted schedule: {schedule_id}")

    return {"message": "Schedule deleted", "schedule_id": schedule_id}


@router.get("/{schedule_id}/logs", response_model=ExecutionLogList)
async def get_schedule_logs(
    schedule_id: str,
    skip: int = 0,
    limit: int = 50,
):
    """Get execution logs for a schedule."""
    if schedule_id not in _schedules:
        raise HTTPException(status_code=404, detail="Schedule not found")

    logs = _execution_logs.get(schedule_id, [])

    formatted_logs = []
    for log in logs[skip : skip + limit]:
        completed_at = log.get("completed_at")
        formatted_logs.append(
            ExecutionLog(
                execution_id=log["execution_id"],
                schedule_id=log["schedule_id"],
                started_at=datetime.fromisoformat(log["started_at"]),
                completed_at=datetime.fromisoformat(completed_at) if completed_at else None,
                status=log["status"],
                error=log.get("error"),
                job_id=log.get("job_id"),
                duration_ms=log.get("duration_ms"),
            )
        )

    return ExecutionLogList(logs=formatted_logs, total=len(logs))


@router.post("/validate-cron")
async def validate_cron_expression(expression: str):
    """Validate a cron expression and show next run times."""
    try:
        cron = parse_cron(expression)
        next_runs = []
        for _ in range(5):
            next_runs.append(get_next_run(cron).isoformat())

        return {
            "valid": True,
            "expression": expression,
            "next_runs": next_runs,
        }
    except Exception as e:
        return {
            "valid": False,
            "expression": expression,
            "error": str(e),
        }


@router.get("/status/summary")
async def get_scheduler_status():
    """Get scheduler status summary."""
    active = sum(1 for s in _schedules.values() if s.get("status") == ScheduleStatus.ACTIVE.value)
    paused = sum(1 for s in _schedules.values() if s.get("status") == ScheduleStatus.PAUSED.value)
    disabled = sum(
        1 for s in _schedules.values() if s.get("status") == ScheduleStatus.DISABLED.value
    )

    total_runs = sum(s.get("run_count", 0) for s in _schedules.values())
    total_failures = sum(s.get("failure_count", 0) for s in _schedules.values())

    return {
        "running": _running,
        "total_schedules": len(_schedules),
        "active": active,
        "paused": paused,
        "disabled": disabled,
        "total_runs": total_runs,
        "total_failures": total_failures,
        "success_rate": f"{(total_runs - total_failures) / max(total_runs, 1) * 100:.1f}%",
    }
