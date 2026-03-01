"""
Prometheus metrics for the platform.

Provides counters, gauges, and histograms for monitoring.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from prometheus_client import Counter, Gauge, Histogram


@dataclass
class MetricsRegistry:
    """
    Central metrics registry.

    Provides access to all platform metrics.
    """

    prefix: str = "qsop"

    # Job metrics
    jobs_submitted: Counter = field(init=False)
    jobs_completed: Counter = field(init=False)
    jobs_failed: Counter = field(init=False)
    jobs_active: Gauge = field(init=False)
    job_duration: Histogram = field(init=False)

    # Quantum metrics
    quantum_circuits_executed: Counter = field(init=False)
    quantum_shots_total: Counter = field(init=False)
    quantum_execution_time: Histogram = field(init=False)

    # Hybrid Performance metrics
    hybrid_iteration_value: Gauge = field(init=False)
    classical_execution_time: Histogram = field(init=False)
    hybrid_loop_duration: Histogram = field(init=False)

    # Crypto metrics
    crypto_operations: Counter = field(init=False)
    crypto_operation_time: Histogram = field(init=False)
    keys_active: Gauge = field(init=False)

    # API metrics
    api_requests: Counter = field(init=False)
    api_latency: Histogram = field(init=False)

    # Workflow metrics
    workflows_started: Counter = field(init=False)
    workflows_completed: Counter = field(init=False)
    workflow_duration: Histogram = field(init=False)
    workflow_step_duration: Histogram = field(init=False)
    workflow_steps_total: Counter = field(init=False)

    def __post_init__(self) -> None:
        """Initialize all metrics."""
        # Job metrics
        self.jobs_submitted = Counter(
            f"{self.prefix}_jobs_submitted_total",
            "Total number of optimization jobs submitted",
            ["algorithm", "backend", "tenant_id"],
        )

        self.jobs_completed = Counter(
            f"{self.prefix}_jobs_completed_total",
            "Total number of optimization jobs completed",
            ["algorithm", "backend", "status", "tenant_id"],
        )

        self.jobs_failed = Counter(
            f"{self.prefix}_jobs_failed_total",
            "Total number of optimization jobs failed",
            ["algorithm", "backend", "error_type", "tenant_id"],
        )

        self.jobs_active = Gauge(
            f"{self.prefix}_jobs_active",
            "Number of currently active jobs",
            ["algorithm", "backend", "tenant_id"],
        )

        self.job_duration = Histogram(
            f"{self.prefix}_job_duration_seconds",
            "Job execution duration in seconds",
            ["algorithm", "backend", "tenant_id"],
            buckets=[1, 5, 10, 30, 60, 120, 300, 600, 1800, 3600],
        )

        # Quantum metrics
        self.quantum_circuits_executed = Counter(
            f"{self.prefix}_quantum_circuits_executed_total",
            "Total number of quantum circuits executed",
            ["backend", "circuit_type", "tenant_id"],
        )

        self.quantum_shots_total = Counter(
            f"{self.prefix}_quantum_shots_total",
            "Total number of measurement shots",
            ["backend", "tenant_id"],
        )

        self.quantum_execution_time = Histogram(
            f"{self.prefix}_quantum_execution_seconds",
            "Quantum circuit execution time",
            ["backend", "tenant_id"],
            buckets=[0.1, 0.5, 1, 2, 5, 10, 30, 60],
        )

        # Hybrid Performance metrics
        self.hybrid_iteration_value = Gauge(
            f"{self.prefix}_hybrid_iteration_value",
            "Current objective value in hybrid optimization loop",
            ["algorithm", "backend", "tenant_id", "job_id"],
        )

        self.classical_execution_time = Histogram(
            f"{self.prefix}_classical_execution_seconds",
            "Classical component execution time in hybrid loop",
            ["algorithm", "backend", "tenant_id"],
            buckets=[0.01, 0.05, 0.1, 0.5, 1, 2, 5, 10],
        )

        self.hybrid_loop_duration = Histogram(
            f"{self.prefix}_hybrid_loop_duration_seconds",
            "Total duration of one hybrid iteration",
            ["algorithm", "backend", "tenant_id"],
            buckets=[0.1, 0.5, 1, 2, 5, 10, 30, 60],
        )

        # Crypto metrics
        self.crypto_operations = Counter(
            f"{self.prefix}_crypto_operations_total",
            "Total cryptographic operations",
            ["operation", "algorithm", "tenant_id"],
        )

        self.crypto_operation_time = Histogram(
            f"{self.prefix}_crypto_operation_seconds",
            "Cryptographic operation duration",
            ["operation", "algorithm", "tenant_id"],
            buckets=[0.001, 0.005, 0.01, 0.05, 0.1, 0.5, 1],
        )

        self.keys_active = Gauge(
            f"{self.prefix}_keys_active",
            "Number of active cryptographic keys",
            ["key_type", "algorithm", "tenant_id"],
        )

        # API metrics
        self.api_requests = Counter(
            f"{self.prefix}_api_requests_total",
            "Total API requests",
            ["method", "endpoint", "status_code", "tenant_id"],
        )

        self.api_latency = Histogram(
            f"{self.prefix}_api_latency_seconds",
            "API request latency",
            ["method", "endpoint", "tenant_id"],
            buckets=[0.01, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5, 10],
        )

        # Workflow metrics
        self.workflows_started = Counter(
            f"{self.prefix}_workflows_started_total",
            "Total workflows started",
            ["definition_id", "name", "tenant_id"],
        )

        self.workflows_completed = Counter(
            f"{self.prefix}_workflows_completed_total",
            "Total workflows completed",
            ["definition_id", "name", "status", "tenant_id"],
        )

        self.workflow_duration = Histogram(
            f"{self.prefix}_workflow_duration_seconds",
            "Workflow execution duration",
            ["definition_id", "name", "status", "tenant_id"],
            buckets=[1, 5, 10, 30, 60, 120, 300, 600, 1800, 3600],
        )

        self.workflow_step_duration = Histogram(
            f"{self.prefix}_workflow_step_duration_seconds",
            "Workflow step duration",
            ["definition_id", "step_id", "status", "tenant_id"],
            buckets=[0.1, 0.5, 1, 2, 5, 10, 30, 60, 120, 300],
        )

        self.workflow_steps_total = Counter(
            f"{self.prefix}_workflow_steps_total",
            "Total workflow steps executed",
            ["definition_id", "step_id", "status", "tenant_id"],
        )


# Global metrics instance
_metrics: MetricsRegistry | None = None


def get_metrics() -> MetricsRegistry:
    """Get the global metrics registry."""
    global _metrics
    if _metrics is None:
        _metrics = MetricsRegistry()
    return _metrics


class MetricsContext:
    """Context manager for timing operations."""

    def __init__(self, histogram: Histogram, labels: dict[str, str]):
        self.histogram = histogram
        self.labels = labels
        self._start_time: float | None = None

    def __enter__(self) -> MetricsContext:
        import time

        self._start_time = time.time()
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        import time

        if self._start_time is not None:
            duration = time.time() - self._start_time
            self.histogram.labels(**self.labels).observe(duration)
