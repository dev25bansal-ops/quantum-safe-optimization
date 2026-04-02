"""
gRPC Server for Quantum-Safe Optimization Platform.

Provides high-performance binary protocol for job submission and streaming.
"""

import asyncio
import json
import os
import time
from datetime import datetime, timezone
from typing import AsyncIterator
from uuid import uuid4

import structlog
from grpc import aio, StatusCode
from grpc_reflection.v1alpha import reflection

from api.grpc import quantum_pb2
from api.grpc import quantum_pb2_grpc
from api.security.enhanced.quantum_encryption import encrypt_with_mlkem
from api.security.enhanced.audit_integrity import sign_audit_entry
from api.security.enhanced.audit_retention import AuditEventType, AuditSeverity, log_audit_event

logger = structlog.get_logger()


class QuantumJobServicer(quantum_pb2_grpc.QuantumJobServiceServicer):
    """gRPC service implementation for quantum jobs."""

    def __init__(self):
        self._jobs: dict[str, dict] = {}
        self._job_results: dict[str, bytes] = {}
        self._progress_subscribers: dict[str, list] = {}

    async def SubmitJob(
        self,
        request: quantum_pb2.SubmitJobRequest,
        context: aio.ServicerContext,
    ) -> quantum_pb2.SubmitJobResponse:
        """Submit a new quantum job."""
        job_id = f"job_{uuid4().hex[:12]}"

        problem_type_map = {
            quantum_pb2.QAOA: "QAOA",
            quantum_pb2.VQE: "VQE",
            quantum_pb2.QUANTUM_ANNEALING: "QuantumAnnealing",
            quantum_pb2.GROVER: "Grover",
            quantum_pb2.QFT: "QFT",
            quantum_pb2.CUSTOM: "Custom",
        }

        job = {
            "job_id": job_id,
            "user_id": request.user_id,
            "tenant_id": request.tenant_id,
            "problem_type": problem_type_map.get(request.problem_type, "QAOA"),
            "problem_config_json": request.problem_config.decode("utf-8"),
            "backend": request.backend or "local_simulator",
            "shots": request.shots or 1024,
            "status": quantum_pb2.QUEUED,
            "created_at": int(time.time()),
            "metadata": dict(request.metadata),
        }

        self._jobs[job_id] = job

        log_audit_event(
            event_type=AuditEventType.JOB_CREATE,
            severity=AuditSeverity.INFO,
            user_id=request.user_id,
            action="grpc_job_submitted",
            resource=job_id,
            details={"backend": request.backend, "problem_type": job["problem_type"]},
        )

        logger.info(
            "grpc_job_submitted",
            job_id=job_id,
            user_id=request.user_id,
            problem_type=job["problem_type"],
        )

        return quantum_pb2.SubmitJobResponse(
            job_id=job_id,
            status=quantum_pb2.QUEUED,
            created_at=job["created_at"],
            estimated_duration_ms=request.shots * 10,
            estimated_cost_usd=request.shots * 0.00001,
        )

    async def GetJob(
        self,
        request: quantum_pb2.GetJobRequest,
        context: aio.ServicerContext,
    ) -> quantum_pb2.GetJobResponse:
        """Get job details and results."""
        job_id = request.job_id

        if job_id not in self._jobs:
            await context.abort(StatusCode.NOT_FOUND, f"Job {job_id} not found")

        job_data = self._jobs[job_id]

        job = quantum_pb2.Job(
            job_id=job_data["job_id"],
            user_id=job_data["user_id"],
            tenant_id=job_data.get("tenant_id", ""),
            problem_type=job_data["problem_type_map"].get(
                job_data["problem_type"], quantum_pb2.QAOA
            ),
            problem_config_json=job_data["problem_config_json"],
            backend=job_data["backend"],
            shots=job_data["shots"],
            status=job_data["status"],
            created_at=job_data["created_at"],
            started_at=job_data.get("started_at", 0),
            completed_at=job_data.get("completed_at", 0),
            cost_usd=job_data.get("cost_usd", 0.0),
            result=self._job_results.get(job_id, b""),
            error_message=job_data.get("error_message", ""),
            metadata=job_data.get("metadata", {}),
        )

        return quantum_pb2.GetJobResponse(job=job)

    async def StreamJobProgress(
        self,
        request: quantum_pb2.JobProgressRequest,
        context: aio.ServicerContext,
    ) -> AsyncIterator[quantum_pb2.JobProgressUpdate]:
        """Stream real-time job progress updates."""
        job_id = request.job_id

        if job_id not in self._jobs:
            await context.abort(StatusCode.NOT_FOUND, f"Job {job_id} not found")

        for i in range(10):
            if context.is_active():
                job_data = self._jobs.get(job_id, {})
                status = job_data.get("status", quantum_pb2.QUEUED)

                yield quantum_pb2.JobProgressUpdate(
                    job_id=job_id,
                    status=status,
                    progress_percent=(i + 1) * 10,
                    current_step=f"Processing layer {i + 1}",
                    elapsed_ms=(i + 1) * 100,
                    remaining_ms=(10 - i - 1) * 100,
                    metrics={"shots_completed": (i + 1) * 100},
                )

                await asyncio.sleep(0.5)

    async def CancelJob(
        self,
        request: quantum_pb2.CancelJobRequest,
        context: aio.ServicerContext,
    ) -> quantum_pb2.CancelJobResponse:
        """Cancel a running job."""
        job_id = request.job_id

        if job_id not in self._jobs:
            await context.abort(StatusCode.NOT_FOUND, f"Job {job_id} not found")

        job_data = self._jobs[job_id]

        if job_data["status"] in (quantum_pb2.COMPLETED, quantum_pb2.FAILED):
            await context.abort(
                StatusCode.FAILED_PRECONDITION,
                f"Cannot cancel job in {job_data['status']} state",
            )

        job_data["status"] = quantum_pb2.CANCELLED
        job_data["completed_at"] = int(time.time())

        log_audit_event(
            event_type=AuditEventType.JOB_CANCEL,
            severity=AuditSeverity.INFO,
            user_id=request.user_id,
            action="grpc_job_cancelled",
            resource=job_id,
        )

        return quantum_pb2.CancelJobResponse(
            success=True,
            message=f"Job {job_id} cancelled successfully",
        )

    async def ListJobs(
        self,
        request: quantum_pb2.ListJobsRequest,
        context: aio.ServicerContext,
    ) -> quantum_pb2.ListJobsResponse:
        """List jobs for a user."""
        jobs = []

        for job_data in self._jobs.values():
            if request.user_id and job_data["user_id"] != request.user_id:
                continue
            if request.tenant_id and job_data.get("tenant_id") != request.tenant_id:
                continue
            if request.status_filter and job_data["status"] != request.status_filter:
                continue

            job = quantum_pb2.Job(
                job_id=job_data["job_id"],
                user_id=job_data["user_id"],
                tenant_id=job_data.get("tenant_id", ""),
                problem_type=quantum_pb2.QAOA,
                problem_config_json=job_data["problem_config_json"],
                backend=job_data["backend"],
                shots=job_data["shots"],
                status=job_data["status"],
                created_at=job_data["created_at"],
            )
            jobs.append(job)

        total_count = len(jobs)
        jobs = jobs[request.offset : request.offset + request.limit] if request.limit else jobs

        return quantum_pb2.ListJobsResponse(jobs=jobs, total_count=total_count)

    async def EstimateCost(
        self,
        request: quantum_pb2.CostEstimateRequest,
        context: aio.ServicerContext,
    ) -> quantum_pb2.CostEstimateResponse:
        """Estimate job cost."""
        base_cost = 0.00001

        shots_cost = request.shots * base_cost
        duration_cost = request.estimated_duration_seconds * 0.0001

        total_cost = shots_cost + duration_cost

        return quantum_pb2.CostEstimateResponse(
            estimated_cost_usd=total_cost,
            cost_breakdown={"shots": shots_cost, "compute": duration_cost},
            currency="USD",
        )

    async def GetBackends(
        self,
        request: quantum_pb2.GetBackendsRequest,
        context: aio.ServicerContext,
    ) -> quantum_pb2.GetBackendsResponse:
        """Get available quantum backends."""
        backends = [
            quantum_pb2.Backend(
                backend_id="local_simulator",
                name="Local Simulator",
                provider="quantum_platform",
                status=quantum_pb2.ONLINE,
                max_qubits=30,
                supported_problems=["QAOA", "VQE", "QFT"],
                cost_per_shot=0.0,
                queue_length=0,
            ),
            quantum_pb2.Backend(
                backend_id="ibm_quantum",
                name="IBM Quantum",
                provider="ibm",
                status=quantum_pb2.ONLINE,
                max_qubits=127,
                supported_problems=["QAOA", "VQE", "Grover"],
                cost_per_shot=0.01,
                queue_length=50,
            ),
            quantum_pb2.Backend(
                backend_id="aws_braket",
                name="AWS Braket",
                provider="aws",
                status=quantum_pb2.ONLINE,
                max_qubits=79,
                supported_problems=["QAOA", "QuantumAnnealing"],
                cost_per_shot=0.005,
                queue_length=20,
            ),
        ]

        return quantum_pb2.GetBackendsResponse(backends=backends)

    async def HealthCheck(
        self,
        request: quantum_pb2.HealthCheckRequest,
        context: aio.ServicerContext,
    ) -> quantum_pb2.HealthCheckResponse:
        """Health check endpoint."""
        return quantum_pb2.HealthCheckResponse(
            status=quantum_pb2.HEALTHY,
            components={
                "grpc": quantum_pb2.ComponentHealth(
                    status=quantum_pb2.HEALTHY,
                    message="gRPC server running",
                    last_check=int(time.time()),
                ),
            },
        )


async def serve(port: int = 50051) -> None:
    """Start gRPC server."""
    server = aio.server()

    quantum_pb2_grpc.add_QuantumJobServiceServicer_to_server(
        QuantumJobServicer(),
        server,
    )

    SERVICE_NAMES = (
        quantum_pb2.DESCRIPTOR.services_by_name["QuantumJobService"].full_name,
        reflection.SERVICE_NAME,
    )
    reflection.enable_server_reflection(SERVICE_NAMES, server)

    server.add_insecure_port(f"[::]:{port}")

    logger.info("grpc_server_starting", port=port)

    await server.start()
    await server.wait_for_termination()


if __name__ == "__main__":
    asyncio.run(serve())
