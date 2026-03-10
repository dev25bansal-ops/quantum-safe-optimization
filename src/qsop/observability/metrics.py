"""Prometheus metrics for quantum optimization platform."""

from __future__ import annotations

import time
from contextlib import contextmanager
from dataclasses import dataclass
from typing import TYPE_CHECKING

from prometheus_client import (
    Counter,
    Gauge,
    Histogram,
    Info,
    CollectorRegistry,
    generate_latest,
    CONTENT_TYPE_LATEST,
    REGISTRY,
)

if TYPE_CHECKING:
    from collections.abc import Iterator


@dataclass
class QuantumMetrics:
    """Central metrics collection for quantum operations."""

    registry: CollectorRegistry

    def __init__(self, registry: CollectorRegistry = REGISTRY, namespace: str = "qsop"):
        """Initialize metrics with custom registry.

        Args:
            registry: Prometheus registry
            namespace: Metric namespace prefix
        """
        self.registry = registry
        self.namespace = namespace
        self._setup_metrics()

    def _setup_metrics(self) -> None:
        """Setup all metrics."""
        ns = self.namespace

        self.jobs_submitted = Counter(
            f"{ns}_jobs_submitted_total",
            "Total number of quantum jobs submitted",
            ["algorithm", "backend", "tenant_id"],
            registry=self.registry,
        )

        self.jobs_completed = Counter(
            f"{ns}_jobs_completed_total",
            "Total number of quantum jobs completed",
            ["algorithm", "backend", "status", "tenant_id"],
            registry=self.registry,
        )

        self.jobs_failed = Counter(
            f"{ns}_jobs_failed_total",
            "Total number of quantum jobs failed",
            ["algorithm", "backend", "error_type", "tenant_id"],
            registry=self.registry,
        )

        self.job_duration = Histogram(
            f"{ns}_job_duration_seconds",
            "Duration of quantum job execution",
            ["algorithm", "backend"],
            buckets=[0.1, 0.5, 1.0, 5.0, 10.0, 30.0, 60.0, 300.0, 600.0],
            registry=self.registry,
        )

        self.queue_depth = Gauge(
            f"{ns}_queue_depth",
            "Current depth of the job queue",
            ["priority", "tenant_id"],
            registry=self.registry,
        )

        self.queue_wait_time = Histogram(
            f"{ns}_queue_wait_seconds",
            "Time jobs spend waiting in queue",
            ["priority"],
            buckets=[0.01, 0.1, 0.5, 1.0, 5.0, 10.0, 30.0],
            registry=self.registry,
        )

        self.active_jobs = Gauge(
            f"{ns}_active_jobs",
            "Number of currently active jobs",
            ["backend", "tenant_id"],
            registry=self.registry,
        )

        self.optimization_iterations = Histogram(
            f"{ns}_optimization_iterations",
            "Number of optimization iterations",
            ["algorithm"],
            buckets=[10, 50, 100, 200, 500, 1000, 2000, 5000],
            registry=self.registry,
        )

        self.circuit_depth = Histogram(
            f"{ns}_circuit_depth",
            "Depth of quantum circuits",
            ["algorithm"],
            buckets=[5, 10, 20, 50, 100, 200, 500],
            registry=self.registry,
        )

        self.circuit_width = Gauge(
            f"{ns}_circuit_width",
            "Number of qubits in circuits",
            ["algorithm"],
            registry=self.registry,
        )

        self.gate_count = Histogram(
            f"{ns}_gate_count",
            "Total gate count in circuits",
            ["algorithm", "gate_type"],
            buckets=[10, 50, 100, 500, 1000, 5000],
            registry=self.registry,
        )

        self.backend_requests = Counter(
            f"{ns}_backend_requests_total",
            "Total requests to quantum backends",
            ["backend", "operation"],
            registry=self.registry,
        )

        self.backend_errors = Counter(
            f"{ns}_backend_errors_total",
            "Total backend errors",
            ["backend", "error_type"],
            registry=self.registry,
        )

        self.backend_latency = Histogram(
            f"{ns}_backend_latency_seconds",
            "Backend request latency",
            ["backend", "operation"],
            buckets=[0.01, 0.05, 0.1, 0.5, 1.0, 5.0, 10.0],
            registry=self.registry,
        )

        self.pqc_operations = Counter(
            f"{ns}_pqc_operations_total",
            "PQC cryptographic operations",
            ["operation", "algorithm"],
            registry=self.registry,
        )

        self.pqc_key_generations = Counter(
            f"{ns}_pqc_key_generations_total",
            "PQC key generations",
            ["algorithm"],
            registry=self.registry,
        )

        self.gpu_utilization = Gauge(
            f"{ns}_gpu_utilization",
            "GPU utilization percentage",
            ["device_id"],
            registry=self.registry,
        )

        self.gpu_memory_used = Gauge(
            f"{ns}_gpu_memory_used_bytes",
            "GPU memory used",
            ["device_id"],
            registry=self.registry,
        )

        self.cost_estimate = Histogram(
            f"{ns}_cost_estimate_dollars",
            "Estimated cost per job",
            ["backend", "algorithm"],
            buckets=[0.01, 0.1, 0.5, 1.0, 5.0, 10.0, 50.0, 100.0],
            registry=self.registry,
        )

        self.error_mitigation_applied = Counter(
            f"{ns}_error_mitigation_applied_total",
            "Error mitigation applications",
            ["method"],
            registry=self.registry,
        )

        self.api_requests = Counter(
            f"{ns}_api_requests_total",
            "Total API requests",
            ["method", "endpoint", "status_code"],
            registry=self.registry,
        )

        self.api_latency = Histogram(
            f"{ns}_api_latency_seconds",
            "API request latency",
            ["method", "endpoint"],
            buckets=[0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0],
            registry=self.registry,
        )

        self.platform_info = Info(
            f"{ns}_platform",
            "Platform information",
            registry=self.registry,
        )
        self.platform_info.info(
            {
                "version": "0.2.0",
                "pqc_enabled": "true",
                "algorithms": "qaoa,vqe,annealing,qnn",
            }
        )

    @contextmanager
    def track_job_execution(
        self,
        algorithm: str,
        backend: str,
        tenant_id: str,
    ) -> Iterator[None]:
        """Context manager to track job execution.

        Args:
            algorithm: Algorithm name
            backend: Backend name
            tenant_id: Tenant identifier
        """
        start_time = time.perf_counter()
        status = "success"
        error_type = None

        try:
            yield
        except Exception as e:
            status = "failed"
            error_type = type(e).__name__
            self.jobs_failed.labels(
                algorithm=algorithm,
                backend=backend,
                error_type=error_type or "unknown",
                tenant_id=tenant_id,
            ).inc()
            raise
        finally:
            duration = time.perf_counter() - start_time
            self.job_duration.labels(
                algorithm=algorithm,
                backend=backend,
            ).observe(duration)
            self.jobs_completed.labels(
                algorithm=algorithm,
                backend=backend,
                status=status,
                tenant_id=tenant_id,
            ).inc()

    def record_optimization_result(
        self,
        algorithm: str,
        iterations: int,
        circuit_depth: int,
        num_qubits: int,
        gate_counts: dict[str, int],
    ) -> None:
        """Record optimization result metrics.

        Args:
            algorithm: Algorithm name
            iterations: Number of iterations
            circuit_depth: Circuit depth
            num_qubits: Number of qubits
            gate_counts: Counts by gate type
        """
        self.optimization_iterations.labels(algorithm=algorithm).observe(iterations)
        self.circuit_depth.labels(algorithm=algorithm).observe(circuit_depth)
        self.circuit_width.labels(algorithm=algorithm).set(num_qubits)

        for gate_type, count in gate_counts.items():
            self.gate_count.labels(
                algorithm=algorithm,
                gate_type=gate_type,
            ).observe(count)

    def record_backend_request(
        self,
        backend: str,
        operation: str,
        latency: float,
        success: bool = True,
        error_type: str | None = None,
    ) -> None:
        """Record backend request metrics.

        Args:
            backend: Backend name
            operation: Operation type
            latency: Request latency in seconds
            success: Whether request succeeded
            error_type: Error type if failed
        """
        self.backend_requests.labels(
            backend=backend,
            operation=operation,
        ).inc()

        self.backend_latency.labels(
            backend=backend,
            operation=operation,
        ).observe(latency)

        if not success and error_type:
            self.backend_errors.labels(
                backend=backend,
                error_type=error_type,
            ).inc()

    def record_pqc_operation(
        self,
        operation: str,
        algorithm: str = "ml-kem-768",
    ) -> None:
        """Record PQC operation.

        Args:
            operation: Operation type (encrypt, decrypt, sign, verify)
            algorithm: PQC algorithm
        """
        self.pqc_operations.labels(
            operation=operation,
            algorithm=algorithm,
        ).inc()

    def record_cost(self, backend: str, algorithm: str, cost: float) -> None:
        """Record estimated cost.

        Args:
            backend: Backend name
            algorithm: Algorithm name
            cost: Estimated cost in dollars
        """
        self.cost_estimate.labels(
            backend=backend,
            algorithm=algorithm,
        ).observe(cost)


_metrics: QuantumMetrics | None = None


def get_metrics_registry() -> CollectorRegistry:
    """Get the Prometheus registry."""
    return REGISTRY


def setup_prometheus(registry: CollectorRegistry = REGISTRY) -> QuantumMetrics:
    """Setup Prometheus metrics.

    Args:
        registry: Prometheus registry

    Returns:
        QuantumMetrics instance
    """
    global _metrics
    if _metrics is None:
        _metrics = QuantumMetrics(registry=registry)
    return _metrics


def get_metrics() -> QuantumMetrics:
    """Get the metrics instance."""
    if _metrics is None:
        return setup_prometheus()
    return _metrics


def get_metrics_text() -> bytes:
    """Generate Prometheus metrics output."""
    return generate_latest(REGISTRY)


__all__ = [
    "QuantumMetrics",
    "get_metrics_registry",
    "setup_prometheus",
    "get_metrics",
    "get_metrics_text",
]
