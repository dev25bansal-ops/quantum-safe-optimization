"""
Prometheus metrics for the platform.

Provides counters, gauges, and histograms for monitoring.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from prometheus_client import Counter, Gauge, Histogram, Info, REGISTRY


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
    
    # Crypto metrics
    crypto_operations: Counter = field(init=False)
    crypto_operation_time: Histogram = field(init=False)
    keys_active: Gauge = field(init=False)
    
    # API metrics
    api_requests: Counter = field(init=False)
    api_latency: Histogram = field(init=False)
    
    def __post_init__(self) -> None:
        """Initialize all metrics."""
        # Job metrics
        self.jobs_submitted = Counter(
            f"{self.prefix}_jobs_submitted_total",
            "Total number of optimization jobs submitted",
            ["algorithm", "backend"],
        )
        
        self.jobs_completed = Counter(
            f"{self.prefix}_jobs_completed_total",
            "Total number of optimization jobs completed",
            ["algorithm", "backend", "status"],
        )
        
        self.jobs_failed = Counter(
            f"{self.prefix}_jobs_failed_total",
            "Total number of optimization jobs failed",
            ["algorithm", "backend", "error_type"],
        )
        
        self.jobs_active = Gauge(
            f"{self.prefix}_jobs_active",
            "Number of currently active jobs",
            ["algorithm", "backend"],
        )
        
        self.job_duration = Histogram(
            f"{self.prefix}_job_duration_seconds",
            "Job execution duration in seconds",
            ["algorithm", "backend"],
            buckets=[1, 5, 10, 30, 60, 120, 300, 600, 1800, 3600],
        )
        
        # Quantum metrics
        self.quantum_circuits_executed = Counter(
            f"{self.prefix}_quantum_circuits_executed_total",
            "Total number of quantum circuits executed",
            ["backend", "circuit_type"],
        )
        
        self.quantum_shots_total = Counter(
            f"{self.prefix}_quantum_shots_total",
            "Total number of measurement shots",
            ["backend"],
        )
        
        self.quantum_execution_time = Histogram(
            f"{self.prefix}_quantum_execution_seconds",
            "Quantum circuit execution time",
            ["backend"],
            buckets=[0.1, 0.5, 1, 2, 5, 10, 30, 60],
        )
        
        # Crypto metrics
        self.crypto_operations = Counter(
            f"{self.prefix}_crypto_operations_total",
            "Total cryptographic operations",
            ["operation", "algorithm"],
        )
        
        self.crypto_operation_time = Histogram(
            f"{self.prefix}_crypto_operation_seconds",
            "Cryptographic operation duration",
            ["operation", "algorithm"],
            buckets=[0.001, 0.005, 0.01, 0.05, 0.1, 0.5, 1],
        )
        
        self.keys_active = Gauge(
            f"{self.prefix}_keys_active",
            "Number of active cryptographic keys",
            ["key_type", "algorithm"],
        )
        
        # API metrics
        self.api_requests = Counter(
            f"{self.prefix}_api_requests_total",
            "Total API requests",
            ["method", "endpoint", "status_code"],
        )
        
        self.api_latency = Histogram(
            f"{self.prefix}_api_latency_seconds",
            "API request latency",
            ["method", "endpoint"],
            buckets=[0.01, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5, 10],
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
