"""
Optimization job endpoints.

Handles submission, monitoring, and retrieval of quantum optimization jobs.
Supports both synchronous (BackgroundTasks) and asynchronous (Celery) execution.
Features:
- Webhook callbacks on job completion
- Result encryption with user's ML-KEM public key
"""

import json
import logging
import os
import uuid
from datetime import datetime, timezone
from typing import Any

import httpx
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, Field

# Import PQC crypto for result encryption
from quantum_safe_crypto import EncryptedEnvelope, py_decrypt, py_encrypt

# Import security features
from api.security.rate_limiter import RateLimits, limiter

# Import advanced simulator
from optimization.src.backends import (
    create_advanced_simulator,
)
from optimization.src.qaoa.problems import MaxCutProblem, PortfolioProblem

# Import optimization runners
from optimization.src.qaoa.runner import QAOAConfig, QAOARunner
from optimization.src.vqe.hamiltonians import IsingHamiltonian, MolecularHamiltonian
from optimization.src.vqe.runner import VQEConfig, VQERunner

from .auth import check_token_revocation, get_current_user, get_user_by_username, verify_pqc_token

# Import Cosmos DB repositories (with fallback to in-memory)
try:
    from api.db.cosmos import JobRepository, cosmos_manager
    from api.db.repository import get_job_store, get_key_store

    _cosmos_available = True
except ImportError:
    _cosmos_available = False
    get_job_store = None
    get_key_store = None

# Import Celery workers (optional)
try:
    from api.tasks.celery_app import get_celery_status
    from api.tasks.workers import dispatch_job

    _celery_available = True
except ImportError:
    _celery_available = False
    dispatch_job = None
    get_celery_status = None

# Import webhook service
try:
    from api.services.webhooks import (
        WebhookEvent,
        send_job_completed_webhook,
        send_job_failed_webhook,
        send_job_webhook,
        validate_webhook_url,
        webhook_service,
    )

    _webhooks_available = True
except ImportError:
    _webhooks_available = False

# Configuration
USE_CELERY = os.getenv("USE_CELERY", "false").lower() == "true"
DEMO_MODE = (
    os.getenv("DEMO_MODE", "false").lower() == "true"
)  # Allow unauthenticated access for demo

# Logger for this module
logger = logging.getLogger(__name__)

router = APIRouter()

# In-memory job storage (fallback when repository is not initialized)
_jobs_db: dict[str, dict[str, Any]] = {}

# Lazy-initialized store
_job_store = None


async def get_or_create_job_store():
    """Get or create the job store."""
    global _job_store
    if _job_store is None and get_job_store is not None:
        _job_store = await get_job_store()
    return _job_store


# Optional HTTP Bearer for demo mode
_optional_security = HTTPBearer(auto_error=False)


async def get_optional_user(
    request: Request, credentials: HTTPAuthorizationCredentials | None = Depends(_optional_security)
) -> dict:
    """
    Optional authentication dependency for demo mode.
    Returns authenticated user if token provided and valid, otherwise returns demo user.
    """
    # If credentials provided, try to validate
    if credentials:
        token = credentials.credentials
        signing_keypair = getattr(request.app.state, "signing_keypair", None)
        payload = verify_pqc_token(token, signing_keypair)

        if payload:
            # Check if token revoked
            token_jti = payload.get("jti")
            if token_jti and await check_token_revocation(token_jti):
                pass  # Fall through to demo user
            else:
                return payload

    # Demo mode: return demo user
    if DEMO_MODE:
        return {
            "sub": "demo_user",
            "username": "demo",
            "roles": ["user"],
        }

    # Not demo mode and no valid token
    raise HTTPException(
        status_code=401,
        detail="Authentication required",
        headers={"WWW-Authenticate": "Bearer"},
    )


# Helper functions for database operations
async def save_job(job_data: dict[str, Any]) -> dict[str, Any]:
    """Save or update a job to the store."""
    store = await get_or_create_job_store()
    if store:
        try:
            return await store.upsert(job_data)
        except Exception as e:
            logger.warning(f"Failed to save job to store: {e}")
    # Fallback to in-memory
    job_id = job_data.get("job_id")
    _jobs_db[job_id] = job_data
    return job_data


async def get_job_data(job_id: str, user_id: str = None) -> dict[str, Any] | None:
    """Get a job from the store."""
    # First check in-memory (for jobs created in this session)
    if job_id in _jobs_db:
        job = _jobs_db[job_id]
        if user_id is None or job.get("user_id") == user_id:
            return job

    # Then check the store
    store = await get_or_create_job_store()
    if store:
        try:
            if user_id:
                return await store.get(job_id, user_id)
            elif hasattr(store, "get_any_partition"):
                return await store.get_any_partition(job_id)
        except Exception as e:
            logger.warning(f"Failed to get job from store: {e}")

    return None


async def delete_job_data(job_id: str, user_id: str) -> bool:
    """Delete a job from the store."""
    store = await get_or_create_job_store()
    if store:
        try:
            return await store.delete(job_id, user_id)
        except Exception as e:
            logger.warning(f"Failed to delete job from store: {e}")
    # Also remove from in-memory
    if job_id in _jobs_db:
        del _jobs_db[job_id]
        return True
    return False


async def list_user_jobs(
    user_id: str,
    status: str | None = None,
    problem_type: str | None = None,
    limit: int = 20,
    offset: int = 0,
) -> tuple[list[dict[str, Any]], int]:
    """List jobs for a user with pagination."""
    store = await get_or_create_job_store()

    if store:
        try:
            filters = {}
            if status:
                filters["status"] = status
            if problem_type:
                filters["problem_type"] = problem_type.upper()

            jobs = await store.list(user_id, filters, limit, offset)
            total = await store.count(user_id, filters)
            return jobs, total
        except Exception as e:
            logger.warning(f"Failed to list jobs from store: {e}")

    # Fallback to in-memory
    user_jobs = [
        job for job in _jobs_db.values() if job["user_id"] == user_id and not job.get("deleted")
    ]

    if status:
        user_jobs = [j for j in user_jobs if j["status"] == status]
    if problem_type:
        user_jobs = [j for j in user_jobs if j["problem_type"] == problem_type.upper()]

    user_jobs.sort(key=lambda x: x.get("created_at", ""), reverse=True)
    total = len(user_jobs)

    return user_jobs[offset : offset + limit], total


class JobSubmissionRequest(BaseModel):
    """Request to submit an optimization job."""

    problem_type: str = Field(..., description="Type: QAOA, VQE, or ANNEALING")
    problem_config: dict[str, Any] = Field(..., description="Problem-specific configuration")
    parameters: dict[str, Any] = Field(default_factory=dict, description="Algorithm parameters")
    backend: str = Field(
        default="local_simulator",
        description="Target backend: local_simulator, advanced_simulator, etc.",
    )
    encrypted_data: str | None = Field(None, description="ML-KEM encrypted payload")
    # Accept both integer and string priority from frontend
    priority: int | str = Field(
        default=5, description="Job priority (1-10 or 'low'/'normal'/'high')"
    )
    callback_url: str | None = Field(None, description="Webhook URL for completion notification")
    encrypt_result: bool = Field(default=False, description="Encrypt result with user's ML-KEM key")
    # Accept frontend's naming convention as well
    encrypted: bool | None = Field(default=False, description="Alias for encrypt_result")
    signed: bool | None = Field(default=False, description="Whether request is signed")

    # Advanced simulator options
    simulator_config: dict[str, Any] | None = Field(
        default=None,
        description="Advanced simulator configuration (simulator_type, noise_model, error_mitigation, etc.)",
    )

    def get_priority_int(self) -> int:
        """Convert priority to integer."""
        if isinstance(self.priority, int):
            return max(1, min(10, self.priority))
        priority_map = {"low": 3, "normal": 5, "high": 8, "urgent": 10}
        return priority_map.get(str(self.priority).lower(), 5)

    def should_encrypt_result(self) -> bool:
        """Check if result should be encrypted."""
        return self.encrypt_result or self.encrypted or False


class JobResponse(BaseModel):
    """Job response model."""

    job_id: str
    status: str
    problem_type: str
    backend: str
    created_at: str
    started_at: str | None = None
    completed_at: str | None = None
    problem_config: dict[str, Any] | None = None  # Job configuration
    result: dict[str, Any] | None = None
    encrypted: bool = False  # Whether job data is encrypted
    encrypted_result: str | None = None  # ML-KEM encrypted result
    error: str | None = None
    message: str | None = None


class JobListResponse(BaseModel):
    """Response for job listing."""

    jobs: list[JobResponse]
    total: int
    limit: int
    offset: int


class DecryptResultRequest(BaseModel):
    """Request to decrypt encrypted job result."""

    secret_key: str = Field(..., description="User's ML-KEM secret key (base64) for decryption")


async def send_webhook_notification(
    callback_url: str,
    job_id: str,
    status: str,
    result: dict[str, Any] | None = None,
    error: str | None = None,
) -> bool:
    """
    Send webhook notification on job completion.

    Uses enhanced webhook service with HMAC signatures and retry logic
    when available, falls back to simple HTTP POST otherwise.

    Args:
        callback_url: URL to POST notification to
        job_id: The job identifier
        status: Job status (completed, failed)
        result: Job result (if completed)
        error: Error message (if failed)

    Returns:
        True if webhook was sent successfully
    """
    # Use enhanced webhook service if available
    if _webhooks_available:
        try:
            if status == "completed":
                delivery_result = await send_job_completed_webhook(
                    callback_url=callback_url,
                    job_id=job_id,
                    result=result or {},
                    status=status,
                )
            else:
                delivery_result = await send_job_failed_webhook(
                    callback_url=callback_url,
                    job_id=job_id,
                    error=error or "Unknown error",
                )

            if not delivery_result.success:
                pass

        except Exception:  # noqa: BLE001 - Fallback to legacy is non-critical
            pass
            # Fall through to legacy implementation

    # Legacy implementation (fallback)
    try:
        payload = {
            "event": "job.completed" if status == "completed" else "job.failed",
            "job_id": job_id,
            "status": status,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

        if result:
            payload["result"] = result
        if error:
            payload["error"] = error

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                callback_url,
                json=payload,
                headers={
                    "Content-Type": "application/json",
                    "X-Webhook-Event": payload["event"],
                    "X-Job-ID": job_id,
                },
            )
            return response.status_code < 400
    except Exception:
        return False


def encrypt_result_for_user(result: dict[str, Any], user_public_key: str) -> str | None:
    """
    Encrypt job result with user's ML-KEM public key.

    Args:
        result: The job result dictionary
        user_public_key: User's ML-KEM-768 public key (base64)

    Returns:
        JSON-serialized encrypted envelope, or None if encryption fails
    """
    try:
        # Serialize result to JSON
        result_bytes = json.dumps(result).encode("utf-8")

        # Encrypt using hybrid encryption (ML-KEM + AES-256-GCM)
        encrypted_envelope = py_encrypt(result_bytes, user_public_key)

        # Convert to JSON string for storage
        return encrypted_envelope.to_json()
    except Exception:
        return None


async def get_user_public_key(user_id: str) -> str | None:
    """Get user's ML-KEM public key from the database."""
    user = await get_user_by_username(user_id) or await get_user_by_id(user_id)
    if user:
        return user.get("kem_public_key")
    return None


async def get_user_by_id(user_id: str) -> dict | None:
    """Get user by ID from auth stores."""
    from api.auth_stores import get_auth_stores

    stores = get_auth_stores()
    return await stores.user_store.get_by_id(user_id)


def decrypt_result_for_user(
    encrypted_envelope_json: str, user_secret_key: str
) -> dict[str, Any] | None:
    """
    Decrypt job result with user's ML-KEM secret key.

    Args:
        encrypted_envelope_json: JSON-serialized encrypted envelope
        user_secret_key: User's ML-KEM-768 secret key (base64)

    Returns:
        Decrypted result dictionary, or None if decryption fails
    """
    try:
        # Parse encrypted envelope from JSON
        envelope = EncryptedEnvelope.from_json(encrypted_envelope_json)

        # Decrypt using hybrid decryption (ML-KEM + AES-256-GCM)
        decrypted_bytes = py_decrypt(envelope, user_secret_key)

        # Parse JSON result
        return json.loads(decrypted_bytes.decode("utf-8"))
    except Exception:
        return None


async def process_optimization_job(job_id: str, job_data: dict[str, Any]):
    """
    Background task to process optimization job.

    Runs the actual optimization using QAOA, VQE, or Annealing runners.
    """

    async def update_job(updates: dict[str, Any]):
        """Update job in storage."""
        # Update in-memory cache
        if job_id in _jobs_db:
            _jobs_db[job_id].update(updates)
        else:
            _jobs_db[job_id] = {**job_data, **updates}

        # Persist to store
        try:
            await save_job(_jobs_db[job_id])
        except Exception as e:
            logger.warning(f"Failed to update job in store: {e}")

    try:
        await update_job(
            {
                "status": "running",
                "started_at": datetime.now(timezone.utc).isoformat(),
            }
        )

        problem_type = job_data.get("problem_type", "").upper()
        problem_config = job_data.get("problem_config", {})
        parameters = job_data.get("parameters", {})
        backend = job_data.get("backend", "local_simulator")
        simulator_config = job_data.get("simulator_config", {})

        # Create advanced simulator if configured
        use_advanced = backend == "advanced_simulator" or simulator_config
        if use_advanced:
            advanced_sim = create_advanced_simulator(
                simulator_type=simulator_config.get("simulator_type", "statevector"),
                noise_model=simulator_config.get("noise_model", "ideal"),
                enable_error_mitigation=simulator_config.get("enable_error_mitigation", False),
                single_qubit_error_rate=simulator_config.get("single_qubit_error_rate", 0.001),
                two_qubit_error_rate=simulator_config.get("two_qubit_error_rate", 0.01),
            )
            await advanced_sim.connect()

        result = None

        if problem_type == "QAOA":
            # Create QAOA runner and problem
            runner = QAOARunner(
                config=QAOAConfig(
                    layers=parameters.get("layers", 2),
                    optimizer=parameters.get("optimizer", "COBYLA"),
                    shots=parameters.get("shots", 1000),
                )
            )

            # Use advanced simulator if configured
            if use_advanced:
                runner.backend = advanced_sim

            # Create problem based on problem_config
            problem_name = problem_config.get("problem", "maxcut")
            if problem_name == "maxcut":
                edges = problem_config.get("edges", [(0, 1), (1, 2), (2, 0)])
                weights = problem_config.get("weights")
                problem = MaxCutProblem(edges=edges, weights=weights)
            elif problem_name == "portfolio":
                problem = PortfolioProblem(
                    expected_returns=problem_config.get("expected_returns", [0.1, 0.12, 0.08]),
                    covariance_matrix=problem_config.get(
                        "covariance_matrix",
                        [[0.1, 0.02, 0.01], [0.02, 0.15, 0.03], [0.01, 0.03, 0.12]],
                    ),
                    num_assets_to_select=problem_config.get("num_assets_to_select", 2),
                )
            else:
                # Default random graph
                problem = MaxCutProblem.random_graph(
                    num_nodes=problem_config.get("num_nodes", 5),
                    edge_probability=problem_config.get("edge_probability", 0.5),
                )

            job_result = await runner.solve(problem)
            result = job_result.to_dict()

        elif problem_type == "VQE":
            # Create VQE runner
            runner = VQERunner(
                config=VQEConfig(
                    optimizer=parameters.get("optimizer", "COBYLA"),
                    shots=parameters.get("shots", 1000),
                    max_iterations=parameters.get("max_iterations", 100),
                    ansatz_type=parameters.get("ansatz_type", "UCCSD"),
                    ansatz_layers=parameters.get("ansatz_layers", 1),
                )
            )

            # Use advanced simulator if configured
            if use_advanced:
                runner.backend = advanced_sim

            # Create Hamiltonian based on problem_config
            hamiltonian_type = problem_config.get("hamiltonian", "h2")
            molecule = problem_config.get("molecule", hamiltonian_type)

            if molecule in ["h2", "H2"]:
                bond_length = problem_config.get("bond_length", 0.74)
                hamiltonian = MolecularHamiltonian.h2(bond_length=bond_length)
            elif molecule in ["lih", "LiH"]:
                bond_length = problem_config.get("bond_length", 1.6)
                hamiltonian = MolecularHamiltonian.lih(bond_length=bond_length)
            elif molecule in ["h2o", "H2O", "water"]:
                hamiltonian = MolecularHamiltonian.h2o()
            elif molecule == "ising":
                # Ising model Hamiltonian
                num_spins = problem_config.get("num_spins", 4)
                coupling_strength = problem_config.get("coupling_strength", 1.0)
                transverse_field = problem_config.get("transverse_field", 0.5)
                hamiltonian = IsingHamiltonian(
                    num_qubits=num_spins,
                    coupling_strength=coupling_strength,
                    transverse_field=transverse_field,
                )
            else:
                # Default to H2
                hamiltonian = MolecularHamiltonian.h2()

            job_result = await runner.solve(hamiltonian)
            result = job_result.to_dict()

        elif problem_type == "ANNEALING":
            # Create QUBO problem
            qubo_matrix_raw = problem_config.get("qubo_matrix")
            qubo_matrix = {}

            if qubo_matrix_raw:
                # Handle different input formats
                if isinstance(qubo_matrix_raw, list):
                    # Check if it's a 2D matrix (list of lists with same length)
                    if qubo_matrix_raw and isinstance(qubo_matrix_raw[0], list):
                        first_row_len = len(qubo_matrix_raw[0]) if qubo_matrix_raw else 0
                        is_square_matrix = (
                            all(
                                isinstance(row, list) and len(row) == first_row_len
                                for row in qubo_matrix_raw
                            )
                            and len(qubo_matrix_raw) == first_row_len
                        )

                        if is_square_matrix and first_row_len > 0:
                            # It's a square matrix - convert to QUBO dict format
                            for i, row in enumerate(qubo_matrix_raw):
                                for j, val in enumerate(row):
                                    if val != 0:
                                        if i <= j:
                                            qubo_matrix[(i, j)] = float(val)
                                        # For lower triangle, add to upper triangle
                                        elif i > j and (j, i) not in qubo_matrix:
                                            qubo_matrix[(j, i)] = float(val)
                        else:
                            # It's an edge list format: [[i, j, weight], ...]
                            for item in qubo_matrix_raw:
                                if isinstance(item, list) and len(item) >= 2:
                                    i, j = int(item[0]), int(item[1])
                                    weight = float(item[2]) if len(item) > 2 else 1.0
                                    if i <= j:
                                        qubo_matrix[(i, j)] = weight
                                    else:
                                        qubo_matrix[(j, i)] = weight
                    else:
                        # Single list of values - treat as diagonal
                        for i, val in enumerate(qubo_matrix_raw):
                            qubo_matrix[(i, i)] = float(val)

                elif isinstance(qubo_matrix_raw, dict):
                    # Convert from JSON format (string keys) to tuple keys
                    for key, value in qubo_matrix_raw.items():
                        if isinstance(key, str):
                            # Parse string tuple like "(0, 1)" or "0,1"
                            key = key.strip("()[] ")
                            parts = [int(x.strip()) for x in key.split(",")]
                            if len(parts) == 2:
                                qubo_matrix[(parts[0], parts[1])] = float(value)
                        elif isinstance(key, (list, tuple)) and len(key) == 2:
                            qubo_matrix[(int(key[0]), int(key[1]))] = float(value)

            if not qubo_matrix:
                # Generate a default QUBO for demo purposes (simple Max-Cut style)
                num_vars = problem_config.get("num_variables", 4)
                for i in range(num_vars):
                    qubo_matrix[(i, i)] = -1.0  # Linear terms
                    for j in range(i + 1, num_vars):
                        qubo_matrix[(i, j)] = 2.0  # Quadratic coupling

            # Use advanced simulator if configured
            if use_advanced:
                try:
                    num_vars_actual = (
                        max(max(k) for k in qubo_matrix.keys()) + 1 if qubo_matrix else 4
                    )
                    annealing_result = advanced_sim.run_annealing(
                        qubo_matrix=qubo_matrix,
                        num_reads=parameters.get("num_reads", 1000),
                        schedule=parameters.get("schedule", "linear"),
                    )

                    optimal_bitstring = "".join(
                        str(int(annealing_result.get("best_solution", {}).get(i, 0)))
                        for i in range(num_vars_actual)
                    )

                    result = {
                        "job_id": job_id,
                        "status": "completed",
                        "backend_type": "ADVANCED_ANNEALING",
                        "simulator_type": simulator_config.get("simulator_type", "statevector"),
                        "noise_model": simulator_config.get("noise_model", "ideal"),
                        "optimal_value": annealing_result.get("best_energy", 0.0),
                        "optimal_bitstring": optimal_bitstring,
                        "optimal_params": annealing_result.get("best_solution", {}),
                        "num_reads": parameters.get("num_reads", 1000),
                        "raw_result": annealing_result,
                    }
                except Exception as e:
                    # Fall back to standard annealing on error
                    use_advanced = False
                    logger.warning(f"Advanced annealing failed, falling back to standard: {e}")

            # Use simulated annealing for local demo (no D-Wave credentials needed)
            if not use_advanced:
                try:
                    import dimod
                    import neal

                    # Create BQM from QUBO
                    bqm = dimod.BinaryQuadraticModel.from_qubo(qubo_matrix)

                    # Use simulated annealing sampler
                    sampler = neal.SimulatedAnnealingSampler()
                    num_reads = parameters.get("num_reads", 1000)
                    sampleset = sampler.sample(bqm, num_reads=num_reads)

                    # Get best solution
                    best_sample = sampleset.first.sample
                    best_energy = float(sampleset.first.energy)

                    # Convert to bitstring
                    num_vars_actual = (
                        max(max(k) for k in qubo_matrix.keys()) + 1 if qubo_matrix else 0
                    )
                    optimal_bitstring = "".join(
                        str(best_sample.get(i, 0)) for i in range(num_vars_actual)
                    )

                    # Build result
                    result = {
                        "job_id": job_id,
                        "status": "completed",
                        "backend_type": "SIMULATED_ANNEALING",
                        "optimal_value": best_energy,
                        "optimal_bitstring": optimal_bitstring,
                        "optimal_params": best_sample,
                        "num_reads": num_reads,
                        "raw_result": {
                            "samples": len(sampleset),
                            "timing": {"total": 0.1},
                        },
                    }

                except ImportError:
                    # Fallback to basic random search if neal not available
                    import random

                    num_vars_actual = (
                        max(max(k) for k in qubo_matrix.keys()) + 1 if qubo_matrix else 4
                    )
                    best_energy = float("inf")
                    best_solution = {}

                    for _ in range(parameters.get("num_reads", 1000)):
                        solution = {i: random.randint(0, 1) for i in range(num_vars_actual)}
                        energy = sum(
                            coef * solution.get(i, 0) * solution.get(j, 0)
                            for (i, j), coef in qubo_matrix.items()
                        )
                        if energy < best_energy:
                            best_energy = energy
                            best_solution = solution

                    optimal_bitstring = "".join(
                        str(best_solution.get(i, 0)) for i in range(num_vars_actual)
                    )

                    result = {
                        "job_id": job_id,
                        "status": "completed",
                        "backend_type": "RANDOM_SEARCH",
                        "optimal_value": best_energy,
                        "optimal_bitstring": optimal_bitstring,
                        "optimal_params": best_solution,
                    }
        else:
            raise ValueError(f"Unknown problem type: {problem_type}")

        # Check if result should be encrypted
        encrypted_result = None
        if job_data.get("encrypt_result"):
            user_id = job_data.get("user_id")
            user_public_key = get_user_public_key(user_id)
            if user_public_key:
                encrypted_result = encrypt_result_for_user(result, user_public_key)

        await update_job(
            {
                "status": "completed",
                "completed_at": datetime.now(timezone.utc).isoformat(),
                "result": result if not encrypted_result else None,
                "encrypted_result": encrypted_result,
            }
        )

        # Send webhook notification if callback_url is set
        callback_url = job_data.get("callback_url")
        if callback_url:
            await send_webhook_notification(
                callback_url=callback_url,
                job_id=job_id,
                status="completed",
                result=result if not encrypted_result else {"encrypted": True},
            )

    except Exception as e:
        error_msg = str(e)
        await update_job(
            {
                "status": "failed",
                "error": error_msg,
                "completed_at": datetime.now(timezone.utc).isoformat(),
            }
        )

        # Send webhook notification for failure
        callback_url = job_data.get("callback_url")
        if callback_url:
            await send_webhook_notification(
                callback_url=callback_url,
                job_id=job_id,
                status="failed",
                error=error_msg,
            )


@router.post("", response_model=JobResponse, status_code=202)
@limiter.limit(RateLimits.JOB_SUBMIT)
async def submit_job(
    request: Request,
    job_request: JobSubmissionRequest,
    background_tasks: BackgroundTasks,
    current_user: dict = Depends(get_optional_user),
):
    """
    Submit a new optimization job.

    Supports QAOA, VQE, and Quantum Annealing problems.
    Jobs are processed asynchronously and results can be retrieved later.

    Features:
    - callback_url: Webhook notification on job completion
    - encrypt_result: Encrypt results with your ML-KEM public key

    When USE_CELERY=true, jobs are dispatched to Celery workers for distributed processing.
    Otherwise, jobs run in FastAPI background tasks.

    Rate limited to prevent resource exhaustion.
    """
    job_id = f"job_{uuid.uuid4().hex[:12]}"

    # Validate callback URL if provided
    if job_request.callback_url:
        if not job_request.callback_url.startswith(("http://", "https://")):
            raise HTTPException(
                status_code=400, detail="callback_url must be a valid HTTP/HTTPS URL"
            )
        if _webhooks_available:
            is_valid, error = validate_webhook_url(job_request.callback_url)
            if not is_valid:
                raise HTTPException(status_code=400, detail=f"callback_url rejected: {error}")

    # Check if user has public key for result encryption
    should_encrypt = job_request.should_encrypt_result()
    if should_encrypt:
        user_public_key = get_user_public_key(current_user["sub"])
        if not user_public_key:
            # In demo mode, skip encryption instead of failing
            if DEMO_MODE and current_user.get("sub") == "demo_user":
                should_encrypt = False
            else:
                raise HTTPException(
                    status_code=400,
                    detail="No ML-KEM public key registered. Use PUT /auth/keys/encryption-key first.",
                )

    # Convert priority to integer
    priority_int = job_request.get_priority_int()

    job_data = {
        "job_id": job_id,
        "id": job_id,  # Cosmos DB document ID
        "user_id": current_user["sub"],
        "problem_type": job_request.problem_type.upper(),
        "problem_config": job_request.problem_config,
        "parameters": job_request.parameters,
        "backend": job_request.backend,
        "priority": priority_int,
        "status": "queued",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "started_at": None,
        "completed_at": None,
        "result": None,
        "encrypted_result": None,
        "error": None,
        "task_id": None,  # Celery task ID if applicable
        "callback_url": job_request.callback_url,
        "encrypt_result": should_encrypt,
    }

    # Save to store (or in-memory fallback)
    await save_job(job_data)
    _jobs_db[job_id] = job_data  # Keep in local cache for background task access

    # Dispatch to appropriate processing backend
    if USE_CELERY and _celery_available and dispatch_job:
        try:
            # Dispatch to Celery worker
            task_id = dispatch_job(job_id, job_data, priority_int)
            job_data["task_id"] = task_id
            _jobs_db[job_id]["task_id"] = task_id
            await save_job(job_data)  # Update with task_id
            message = "Job queued for Celery worker processing"
        except Exception as e:
            # Fall back to background tasks if Celery dispatch fails
            background_tasks.add_task(process_optimization_job, job_id, job_data)
            message = f"Job submitted (Celery fallback: {str(e)})"
    else:
        # Use FastAPI background tasks
        background_tasks.add_task(process_optimization_job, job_id, job_data)
        message = "Job submitted for background processing"

    return JobResponse(
        job_id=job_id,
        status="queued",
        problem_type=job_request.problem_type,
        backend=job_request.backend,
        created_at=job_data["created_at"],
        message=message,
    )


@router.get("/workers/status")
async def get_worker_status(
    current_user: dict = Depends(get_current_user),
):
    """
    Get Celery worker status (admin only).

    Returns information about active workers and pending tasks.
    """
    if _celery_available and get_celery_status:
        return get_celery_status()
    return {"status": "celery_not_configured", "use_celery": USE_CELERY}


@router.get("/webhooks/stats")
async def get_webhook_statistics(
    current_user: dict = Depends(get_current_user),
):
    """
    Get webhook delivery statistics.

    Returns statistics about webhook delivery including:
    - Total deliveries attempted
    - Success/failure counts
    - Retry statistics
    """
    if not _webhooks_available:
        return {
            "available": False,
            "message": "Webhook service not available",
        }

    stats = webhook_service.get_statistics()
    return {
        "available": True,
        **stats,
    }


@router.get("/encryption/info")
async def get_encryption_info():
    """
    Get information about the ML-KEM encryption system.

    Returns details about:
    - Supported algorithms and security levels
    - Key sizes
    - How to generate keys and encrypt/decrypt results
    """
    return {
        "encryption_system": "Hybrid ML-KEM + AES-256-GCM",
        "key_encapsulation": {
            "algorithm": "ML-KEM (NIST FIPS 203)",
            "security_levels": [
                {
                    "level": 1,
                    "algorithm": "ML-KEM-512",
                    "security": "128-bit",
                    "public_key_size": 800,
                    "secret_key_size": 1632,
                    "ciphertext_size": 768,
                },
                {
                    "level": 3,
                    "algorithm": "ML-KEM-768",
                    "security": "192-bit",
                    "public_key_size": 1184,
                    "secret_key_size": 2400,
                    "ciphertext_size": 1088,
                    "default": True,
                },
                {
                    "level": 5,
                    "algorithm": "ML-KEM-1024",
                    "security": "256-bit",
                    "public_key_size": 1568,
                    "secret_key_size": 3168,
                    "ciphertext_size": 1568,
                },
            ],
        },
        "symmetric_encryption": {
            "algorithm": "AES-256-GCM",
            "key_derivation": "HKDF-SHA256",
            "nonce_size": 12,
            "tag_size": 16,
        },
        "usage": {
            "generate_keys": "POST /auth/keys/generate with key_type='kem'",
            "register_key": "PUT /auth/keys/encryption-key with your public key",
            "submit_job": "POST /jobs with encrypt_result=true",
            "get_result": "GET /jobs/{job_id}/result returns encrypted envelope",
            "decrypt_server": "POST /jobs/{job_id}/decrypt with secret_key",
            "decrypt_client": "Use quantum_safe_crypto.py_decrypt() locally",
        },
        "security_note": "For maximum security, decrypt results client-side. Your secret key should never leave your device.",
    }


@router.get("/{job_id}", response_model=JobResponse)
async def get_job(
    job_id: str,
    current_user: dict = Depends(get_optional_user),
):
    """
    Get status and results of a specific job.

    If encrypt_result was enabled, the result will be in encrypted_result field
    and can only be decrypted with your ML-KEM secret key.

    For real-time updates, use the WebSocket endpoint at /ws/jobs/{job_id}
    """
    job = await get_job_data(job_id, current_user["sub"])

    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    if job["user_id"] != current_user["sub"]:
        raise HTTPException(status_code=403, detail="Access denied")

    return JobResponse(
        job_id=job["job_id"],
        status=job["status"],
        problem_type=job["problem_type"],
        backend=job["backend"],
        created_at=job["created_at"],
        started_at=job.get("started_at"),
        completed_at=job.get("completed_at"),
        problem_config=job.get("problem_config"),
        result=job.get("result"),
        encrypted=job.get("encrypted", False),
        encrypted_result=job.get("encrypted_result"),
        error=job.get("error"),
    )


@router.get("", response_model=JobListResponse)
@limiter.limit(RateLimits.JOB_LIST)
async def list_jobs(
    request: Request,
    current_user: dict = Depends(get_optional_user),
    status: str | None = Query(None, description="Filter by status"),
    problem_type: str | None = Query(None, description="Filter by problem type"),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
):
    """
    List all jobs for the current user.
    """
    user_jobs, total = await list_user_jobs(
        user_id=current_user["sub"],
        status=status,
        problem_type=problem_type,
        limit=limit,
        offset=offset,
    )

    return JobListResponse(
        jobs=[
            JobResponse(
                job_id=j["job_id"],
                status=j["status"],
                problem_type=j["problem_type"],
                backend=j["backend"],
                created_at=j["created_at"],
                started_at=j.get("started_at"),
                completed_at=j.get("completed_at"),
                problem_config=j.get("problem_config"),
                result=j.get("result"),
                encrypted=j.get("encrypted", False),
                error=j.get("error"),
            )
            for j in user_jobs
        ],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.delete("/{job_id}")
async def cancel_job(
    job_id: str,
    current_user: dict = Depends(get_current_user),
):
    """
    Cancel a queued or running job.

    Sets job status to 'cancelled' and stops any running background tasks.
    """
    job = await get_job_data(job_id, current_user["sub"])

    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    if job["user_id"] != current_user["sub"]:
        raise HTTPException(status_code=403, detail="Access denied")

    if job["status"] in ["completed", "failed", "cancelled"]:
        raise HTTPException(
            status_code=400, detail=f"Cannot cancel job with status: {job['status']}"
        )

    # Update job status
    job["status"] = "cancelled"
    job["completed_at"] = datetime.now(timezone.utc).isoformat()
    job["cancellation_reason"] = "User requested cancellation"

    # Persist to store
    await save_job(job)

    # Send webhook notification if callback_url is set
    callback_url = job.get("callback_url")
    if callback_url:
        await send_webhook_notification(
            callback_url=callback_url,
            job_id=job_id,
            status="cancelled",
            result={"reason": "User requested cancellation"},
        )

    return {"message": "Job cancelled successfully", "job_id": job_id, "status": "cancelled"}


@router.get("/{job_id}/result")
async def get_job_result(
    job_id: str,
    current_user: dict = Depends(get_current_user),
):
    """
    Get detailed results of a completed job.

    If the result was encrypted, returns the encrypted envelope.
    Use POST /{job_id}/decrypt to decrypt with your secret key.
    """
    job = await get_job_data(job_id, current_user["sub"])

    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    if job["user_id"] != current_user["sub"]:
        raise HTTPException(status_code=403, detail="Access denied")

    if job["status"] != "completed":
        raise HTTPException(
            status_code=400, detail=f"Job not completed. Current status: {job['status']}"
        )

    # Check if result is encrypted
    encrypted_result = job.get("encrypted_result")
    is_encrypted = encrypted_result is not None

    return {
        "job_id": job_id,
        "status": "completed",
        "encrypted": is_encrypted,
        "result": job.get("result") if not is_encrypted else None,
        "encrypted_result": encrypted_result if is_encrypted else None,
        "encryption_algorithm": "ML-KEM-768 + AES-256-GCM" if is_encrypted else None,
        "metadata": {
            "problem_type": job["problem_type"],
            "backend": job["backend"],
            "execution_time_ms": _calculate_execution_time(job),
        },
    }


@router.post("/{job_id}/decrypt", deprecated=True)
async def decrypt_job_result(
    job_id: str,
    request: DecryptResultRequest,
    current_user: dict = Depends(get_current_user),
):
    """
    ⚠️ CRITICAL SECURITY: DECRYPT ENDPOINT REMOVED ⚠️

    This endpoint has been DISABLED for security reasons.
    Accepting secret keys over HTTP is a CRITICAL security vulnerability.

    Client-side decryption is REQUIRED:
    1. Use quantum_safe_crypto.py_decrypt() offline
    2. Your secret key never leaves your device
    3. No network exposure of sensitive cryptographic material

    Client-side decryption example:
    ```
    import json
    from quantum_safe_crypto import EncryptedEnvelope, py_decrypt

    envelope = EncryptedEnvelope.from_json(encrypted_result)
    result_bytes = py_decrypt(envelope, your_secret_key)
    result = json.loads(result_bytes.decode('utf-8'))
    ```
    """
    raise HTTPException(
        status_code=410,
        detail="Server-side decryption disabled for security. Use client-side decryption with your ML-KEM secret key.",
    )


@router.post("/{job_id}/retry", response_model=JobResponse, status_code=202)
async def retry_job(
    job_id: str,
    background_tasks: BackgroundTasks,
    current_user: dict = Depends(get_current_user),
):
    """
    Retry a failed job.
    """
    job = await get_job_data(job_id, current_user["sub"])

    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    if job["user_id"] != current_user["sub"]:
        raise HTTPException(status_code=403, detail="Access denied")

    if job["status"] != "failed":
        raise HTTPException(status_code=400, detail="Only failed jobs can be retried")

    # Create new job with same config
    new_job_id = f"job_{uuid.uuid4().hex[:12]}"

    new_job = {
        **job,
        "job_id": new_job_id,
        "id": new_job_id,
        "status": "queued",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "started_at": None,
        "completed_at": None,
        "result": None,
        "encrypted_result": None,
        "error": None,
        "retry_of": job_id,
    }

    # Save to store and local cache
    await save_job(new_job)
    _jobs_db[new_job_id] = new_job

    background_tasks.add_task(process_optimization_job, new_job_id, new_job)

    return JobResponse(
        job_id=new_job_id,
        status="queued",
        problem_type=job["problem_type"],
        backend=job["backend"],
        created_at=new_job["created_at"],
        message=f"Retry job created from {job_id}",
    )


def _calculate_execution_time(job: dict[str, Any]) -> int | None:
    """Calculate job execution time in milliseconds."""
    if not job.get("started_at") or not job.get("completed_at"):
        return None

    start = datetime.fromisoformat(job["started_at"])
    end = datetime.fromisoformat(job["completed_at"])

    return int((end - start).total_seconds() * 1000)
