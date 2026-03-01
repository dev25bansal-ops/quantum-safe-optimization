"""
Celery application configuration.

Uses Redis as message broker for job queue management.
"""

import os

from celery import Celery

# Redis configuration
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")
CELERY_BROKER_URL = os.getenv("CELERY_BROKER_URL", f"{REDIS_URL}/0")
CELERY_RESULT_BACKEND = os.getenv("CELERY_RESULT_BACKEND", f"{REDIS_URL}/1")

# Create Celery app
celery_app = Celery(
    "quantum_optimization",
    broker=CELERY_BROKER_URL,
    backend=CELERY_RESULT_BACKEND,
    include=["api.tasks.workers"],
)

# Celery configuration
celery_app.conf.update(
    # Task settings
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    # Task execution settings
    task_acks_late=True,  # Acknowledge after task completion
    task_reject_on_worker_lost=True,  # Re-queue if worker dies
    # Result backend settings
    result_expires=86400,  # Results expire after 24 hours
    result_extended=True,  # Store task metadata
    # Worker settings
    worker_prefetch_multiplier=1,  # One task at a time for fairness
    worker_concurrency=4,  # Number of concurrent workers
    # Task time limits
    task_soft_time_limit=300,  # 5 minutes soft limit
    task_time_limit=600,  # 10 minutes hard limit
    # Task routing based on priority
    task_routes={
        "api.tasks.workers.process_qaoa_job": {"queue": "optimization"},
        "api.tasks.workers.process_vqe_job": {"queue": "optimization"},
        "api.tasks.workers.process_annealing_job": {"queue": "optimization"},
        "api.tasks.workers.send_job_update": {"queue": "notifications"},
    },
    # Priority queues
    task_queues={
        "optimization": {
            "exchange": "optimization",
            "routing_key": "optimization",
        },
        "notifications": {
            "exchange": "notifications",
            "routing_key": "notifications",
        },
    },
    # Beat schedule for periodic tasks (optional)
    beat_schedule={
        "cleanup-expired-jobs": {
            "task": "api.tasks.workers.cleanup_expired_jobs",
            "schedule": 3600.0,  # Every hour
        },
    },
)


def get_celery_status() -> dict:
    """Get Celery worker status."""
    try:
        inspect = celery_app.control.inspect()
        stats = inspect.stats()
        active = inspect.active()
        reserved = inspect.reserved()

        return {
            "status": "connected",
            "workers": list(stats.keys()) if stats else [],
            "active_tasks": sum(len(t) for t in active.values()) if active else 0,
            "reserved_tasks": sum(len(t) for t in reserved.values()) if reserved else 0,
        }
    except Exception as e:
        return {
            "status": "disconnected",
            "error": str(e),
        }
