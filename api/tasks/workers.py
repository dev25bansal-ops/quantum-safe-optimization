"""
Celery task workers for optimization job execution.

Moves job processing to background workers for scalability.
"""

import asyncio
import json
import os
from datetime import datetime, timezone
from typing import Any

import redis
from celery import Task
from celery.exceptions import SoftTimeLimitExceeded

from .celery_app import celery_app

# Redis client for job state and WebSocket notifications
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")


class OptimizationTask(Task):
    """
    Base task class with retry and error handling.
    """

    autoretry_for = (ConnectionError, TimeoutError)
    retry_backoff = True
    retry_backoff_max = 600  # Max 10 minutes between retries
    retry_jitter = True
    max_retries = 3

    _redis_client: redis.Redis | None = None

    @property
    def redis_client(self) -> redis.Redis:
        """Lazy Redis client initialization."""
        if self._redis_client is None:
            self._redis_client = redis.from_url(REDIS_URL, decode_responses=True)
        return self._redis_client

    def publish_progress(self, job_id: str, progress: dict[str, Any]):
        """Publish job progress to Redis pub/sub for WebSocket streaming."""
        channel = f"job:{job_id}:progress"
        self.redis_client.publish(channel, json.dumps(progress))

    def update_job_state(self, job_id: str, state: dict[str, Any]):
        """Update job state in Redis for persistence."""
        key = f"job:{job_id}:state"
        self.redis_client.hset(
            key,
            mapping={
                k: json.dumps(v) if isinstance(v, (dict, list)) else str(v)
                for k, v in state.items()
            },
        )
        # Set expiry for cleanup (24 hours)
        self.redis_client.expire(key, 86400)

    def get_job_state(self, job_id: str) -> dict[str, Any] | None:
        """Get job state from Redis."""
        key = f"job:{job_id}:state"
        data = self.redis_client.hgetall(key)
        if data:
            return {
                k: json.loads(v) if v.startswith("{") or v.startswith("[") else v
                for k, v in data.items()
            }
        return None


def run_async(coro):
    """Run async function in sync context."""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


@celery_app.task(bind=True, base=OptimizationTask, name="api.tasks.workers.process_qaoa_job")
def process_qaoa_job(
    self: OptimizationTask,
    job_id: str,
    job_data: dict[str, Any],
) -> dict[str, Any]:
    """
    Process a QAOA optimization job.

    Args:
        job_id: Unique job identifier
        job_data: Job configuration and problem parameters

    Returns:
        Job result dictionary
    """
    from optimization.src.qaoa.problems import MaxCutProblem, PortfolioProblem
    from optimization.src.qaoa.runner import QAOAConfig, QAOARunner

    try:
        # Update job status to running
        self.update_job_state(
            job_id,
            {
                "status": "running",
                "started_at": datetime.now(timezone.utc).isoformat(),
                "worker": self.request.hostname,
                "task_id": self.request.id,
            },
        )
        self.publish_progress(
            job_id,
            {
                "status": "running",
                "message": "Job started on worker",
                "progress": 0,
            },
        )

        problem_config = job_data.get("problem_config", {})
        parameters = job_data.get("parameters", {})

        # Create QAOA runner
        runner = QAOARunner(
            config=QAOAConfig(
                layers=parameters.get("layers", 2),
                optimizer=parameters.get("optimizer", "COBYLA"),
                shots=parameters.get("shots", 1000),
            )
        )

        # Progress callback
        def on_progress(iteration: int, cost: float, total_iterations: int):
            progress = int((iteration / total_iterations) * 100) if total_iterations > 0 else 0
            self.publish_progress(
                job_id,
                {
                    "status": "running",
                    "message": f"Iteration {iteration}/{total_iterations}",
                    "progress": progress,
                    "current_cost": cost,
                },
            )

        # Create problem based on config
        problem_name = problem_config.get("problem", "maxcut")
        if problem_name == "maxcut":
            edges = problem_config.get("edges", [(0, 1), (1, 2), (2, 0)])
            weights = problem_config.get("weights")
            problem = MaxCutProblem(edges=edges, weights=weights)
        elif problem_name == "portfolio":
            problem = PortfolioProblem(
                expected_returns=problem_config.get("expected_returns", [0.1, 0.12, 0.08]),
                covariance_matrix=problem_config.get("covariance_matrix"),
                num_assets_to_select=problem_config.get("num_assets_to_select", 2),
            )
        else:
            problem = MaxCutProblem.random_graph(
                num_nodes=problem_config.get("num_nodes", 5),
                edge_probability=problem_config.get("edge_probability", 0.5),
            )

        self.publish_progress(
            job_id,
            {
                "status": "running",
                "message": "Problem constructed, starting optimization",
                "progress": 10,
            },
        )

        # Run optimization
        result = run_async(runner.solve(problem))
        result_dict = result.to_dict()

        # Update final state
        self.update_job_state(
            job_id,
            {
                "status": "completed",
                "completed_at": datetime.now(timezone.utc).isoformat(),
                "result": result_dict,
            },
        )
        self.publish_progress(
            job_id,
            {
                "status": "completed",
                "message": "Optimization complete",
                "progress": 100,
                "result": result_dict,
            },
        )

        return {
            "job_id": job_id,
            "status": "completed",
            "result": result_dict,
        }

    except SoftTimeLimitExceeded:
        error_msg = "Job exceeded time limit"
        self.update_job_state(
            job_id,
            {
                "status": "failed",
                "error": error_msg,
                "completed_at": datetime.now(timezone.utc).isoformat(),
            },
        )
        self.publish_progress(
            job_id,
            {
                "status": "failed",
                "message": error_msg,
                "progress": -1,
            },
        )
        raise

    except Exception as e:
        error_msg = str(e)
        self.update_job_state(
            job_id,
            {
                "status": "failed",
                "error": error_msg,
                "completed_at": datetime.now(timezone.utc).isoformat(),
            },
        )
        self.publish_progress(
            job_id,
            {
                "status": "failed",
                "message": error_msg,
                "progress": -1,
            },
        )
        raise


@celery_app.task(bind=True, base=OptimizationTask, name="api.tasks.workers.process_vqe_job")
def process_vqe_job(
    self: OptimizationTask,
    job_id: str,
    job_data: dict[str, Any],
) -> dict[str, Any]:
    """
    Process a VQE (Variational Quantum Eigensolver) job.
    """
    from optimization.src.vqe.runner import VQEConfig, VQERunner

    try:
        self.update_job_state(
            job_id,
            {
                "status": "running",
                "started_at": datetime.now(timezone.utc).isoformat(),
                "worker": self.request.hostname,
            },
        )
        self.publish_progress(
            job_id,
            {
                "status": "running",
                "message": "VQE job started",
                "progress": 0,
            },
        )

        problem_config = job_data.get("problem_config", {})
        parameters = job_data.get("parameters", {})

        # Create VQE runner
        runner = VQERunner(
            config=VQEConfig(
                optimizer=parameters.get("optimizer", "COBYLA"),
                shots=parameters.get("shots", 1000),
                max_iterations=parameters.get("max_iterations", 200),
                ansatz_type=parameters.get("ansatz_type", "hardware_efficient"),
            )
        )

        self.publish_progress(
            job_id,
            {
                "status": "running",
                "message": "Running VQE optimization",
                "progress": 20,
            },
        )

        # Run VQE for molecule
        hamiltonian_type = problem_config.get("hamiltonian", "h2")
        result = run_async(runner.solve_molecule(hamiltonian_type))
        result_dict = result.to_dict()

        self.update_job_state(
            job_id,
            {
                "status": "completed",
                "completed_at": datetime.now(timezone.utc).isoformat(),
                "result": result_dict,
            },
        )
        self.publish_progress(
            job_id,
            {
                "status": "completed",
                "message": "VQE optimization complete",
                "progress": 100,
                "result": result_dict,
            },
        )

        return {
            "job_id": job_id,
            "status": "completed",
            "result": result_dict,
        }

    except Exception as e:
        error_msg = str(e)
        self.update_job_state(
            job_id,
            {
                "status": "failed",
                "error": error_msg,
                "completed_at": datetime.now(timezone.utc).isoformat(),
            },
        )
        self.publish_progress(
            job_id,
            {
                "status": "failed",
                "message": error_msg,
                "progress": -1,
            },
        )
        raise


@celery_app.task(bind=True, base=OptimizationTask, name="api.tasks.workers.process_annealing_job")
def process_annealing_job(
    self: OptimizationTask,
    job_id: str,
    job_data: dict[str, Any],
) -> dict[str, Any]:
    """
    Process a Quantum Annealing job.
    """
    from optimization.src.annealing.problems import QUBOProblem
    from optimization.src.annealing.runner import AnnealingConfig, AnnealingRunner

    try:
        self.update_job_state(
            job_id,
            {
                "status": "running",
                "started_at": datetime.now(timezone.utc).isoformat(),
                "worker": self.request.hostname,
            },
        )
        self.publish_progress(
            job_id,
            {
                "status": "running",
                "message": "Annealing job started",
                "progress": 0,
            },
        )

        problem_config = job_data.get("problem_config", {})
        parameters = job_data.get("parameters", {})

        # Create Annealing runner
        runner = AnnealingRunner(
            config=AnnealingConfig(
                num_reads=parameters.get("num_reads", 1000),
                use_hybrid=parameters.get("use_hybrid", True),
                time_limit=parameters.get("time_limit", 60),
            )
        )

        # Create QUBO problem
        qubo_matrix = problem_config.get("qubo_matrix")
        if not qubo_matrix:
            raise ValueError("ANNEALING requires qubo_matrix in problem_config")

        problem = QUBOProblem(qubo_matrix)

        self.publish_progress(
            job_id,
            {
                "status": "running",
                "message": "Running quantum annealing",
                "progress": 30,
            },
        )

        result = run_async(runner.solve(problem))
        result_dict = result.to_dict()

        self.update_job_state(
            job_id,
            {
                "status": "completed",
                "completed_at": datetime.now(timezone.utc).isoformat(),
                "result": result_dict,
            },
        )
        self.publish_progress(
            job_id,
            {
                "status": "completed",
                "message": "Annealing complete",
                "progress": 100,
                "result": result_dict,
            },
        )

        return {
            "job_id": job_id,
            "status": "completed",
            "result": result_dict,
        }

    except Exception as e:
        error_msg = str(e)
        self.update_job_state(
            job_id,
            {
                "status": "failed",
                "error": error_msg,
                "completed_at": datetime.now(timezone.utc).isoformat(),
            },
        )
        self.publish_progress(
            job_id,
            {
                "status": "failed",
                "message": error_msg,
                "progress": -1,
            },
        )
        raise


@celery_app.task(bind=True, base=OptimizationTask, name="api.tasks.workers.send_job_update")
def send_job_update(
    self: OptimizationTask,
    job_id: str,
    update: dict[str, Any],
) -> bool:
    """
    Send a job update notification via pub/sub.
    Used for manual status updates.
    """
    self.publish_progress(job_id, update)
    return True


@celery_app.task(name="api.tasks.workers.cleanup_expired_jobs")
def cleanup_expired_jobs() -> dict[str, int]:
    """
    Periodic task to clean up expired job data from Redis.
    """
    client = redis.from_url(REDIS_URL, decode_responses=True)

    # Scan for job state keys
    cursor = 0
    cleaned = 0

    while True:
        cursor, keys = client.scan(cursor=cursor, match="job:*:state", count=100)
        for key in keys:
            # Check if TTL is already set
            ttl = client.ttl(key)
            if ttl == -1:  # No expiry set
                client.expire(key, 86400)
                cleaned += 1

        if cursor == 0:
            break

    return {"cleaned_keys": cleaned}


def dispatch_job(job_id: str, job_data: dict[str, Any], priority: int = 5) -> str:
    """
    Dispatch a job to the appropriate worker based on problem type.

    Args:
        job_id: Unique job identifier
        job_data: Job configuration
        priority: Job priority (1-10, lower is higher priority)

    Returns:
        Celery task ID
    """
    problem_type = job_data.get("problem_type", "").upper()

    # Map problem types to tasks
    task_map = {
        "QAOA": process_qaoa_job,
        "VQE": process_vqe_job,
        "ANNEALING": process_annealing_job,
    }

    task = task_map.get(problem_type)
    if not task:
        raise ValueError(f"Unknown problem type: {problem_type}")

    # Submit task with priority
    # Celery priority: 0 is highest, 9 is lowest
    celery_priority = 10 - priority  # Convert to Celery's inverted scale

    result = task.apply_async(
        args=[job_id, job_data],
        priority=celery_priority,
        queue="optimization",
    )

    return result.id
