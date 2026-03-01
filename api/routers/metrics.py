"""
Prometheus metrics endpoint for monitoring and alerting.

Provides:
- HTTP request metrics (count, latency, status codes)
- Job processing metrics (count, duration, status)
- PQC cryptographic operation metrics
- WebSocket connection metrics
- System health metrics
"""

import asyncio
import time
from collections.abc import Callable
from functools import wraps
from typing import Any

from fastapi import APIRouter, Request, Response
from fastapi.responses import PlainTextResponse
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint

router = APIRouter()


class PrometheusMetrics:
    """
    Prometheus metrics collector.

    Collects and exposes metrics in Prometheus text format.
    Thread-safe using simple counters (suitable for single-process uvicorn).

    For multi-process deployments, use prometheus_client with multiprocess mode
    or a shared metrics backend.
    """

    def __init__(self, namespace: str = "quantum_api"):
        self.namespace = namespace
        self._start_time = time.time()

        # Request metrics
        self._request_count: dict[str, int] = {}  # {method_path_status: count}
        self._request_latency_sum: dict[str, float] = {}  # {method_path: sum}
        self._request_latency_count: dict[str, int] = {}  # {method_path: count}

        # Job metrics
        self._jobs_total: dict[str, int] = {}  # {problem_type_status: count}
        self._jobs_duration_sum: dict[str, float] = {}  # {problem_type: sum}
        self._jobs_duration_count: dict[str, int] = {}  # {problem_type: count}
        self._jobs_in_progress: dict[str, int] = {}  # {problem_type: count}

        # PQC metrics
        self._pqc_operations: dict[str, int] = {}  # {operation_level: count}
        self._pqc_latency_sum: dict[str, float] = {}  # {operation: sum}
        self._pqc_latency_count: dict[str, int] = {}  # {operation: count}

        # WebSocket metrics
        self._ws_connections_total: int = 0
        self._ws_connections_active: int = 0
        self._ws_messages_received: int = 0
        self._ws_messages_sent: int = 0

        # Error metrics
        self._errors_total: dict[str, int] = {}  # {error_type: count}

    def record_request(
        self,
        method: str,
        path: str,
        status_code: int,
        duration_seconds: float,
    ):
        """Record an HTTP request."""
        # Normalize path (remove IDs, keep structure)
        normalized_path = self._normalize_path(path)

        # Request count by method, path, status
        key = f"{method}_{normalized_path}_{status_code}"
        self._request_count[key] = self._request_count.get(key, 0) + 1

        # Latency histogram (simplified as sum/count)
        latency_key = f"{method}_{normalized_path}"
        self._request_latency_sum[latency_key] = (
            self._request_latency_sum.get(latency_key, 0) + duration_seconds
        )
        self._request_latency_count[latency_key] = (
            self._request_latency_count.get(latency_key, 0) + 1
        )

    def record_job_started(self, problem_type: str):
        """Record a job being started."""
        self._jobs_in_progress[problem_type] = self._jobs_in_progress.get(problem_type, 0) + 1

    def record_job_completed(
        self,
        problem_type: str,
        status: str,
        duration_seconds: float,
    ):
        """Record a job completion."""
        # Decrease in-progress count
        self._jobs_in_progress[problem_type] = max(
            0, self._jobs_in_progress.get(problem_type, 0) - 1
        )

        # Job count by type and status
        key = f"{problem_type}_{status}"
        self._jobs_total[key] = self._jobs_total.get(key, 0) + 1

        # Duration histogram
        self._jobs_duration_sum[problem_type] = (
            self._jobs_duration_sum.get(problem_type, 0) + duration_seconds
        )
        self._jobs_duration_count[problem_type] = self._jobs_duration_count.get(problem_type, 0) + 1

    def record_pqc_operation(
        self,
        operation: str,
        security_level: int,
        duration_seconds: float,
    ):
        """Record a PQC cryptographic operation."""
        key = f"{operation}_{security_level}"
        self._pqc_operations[key] = self._pqc_operations.get(key, 0) + 1

        # Latency
        self._pqc_latency_sum[operation] = (
            self._pqc_latency_sum.get(operation, 0) + duration_seconds
        )
        self._pqc_latency_count[operation] = self._pqc_latency_count.get(operation, 0) + 1

    def record_ws_connection(self, connected: bool):
        """Record WebSocket connection/disconnection."""
        self._ws_connections_total += 1 if connected else 0
        self._ws_connections_active += 1 if connected else -1
        self._ws_connections_active = max(0, self._ws_connections_active)

    def record_ws_message(self, sent: bool):
        """Record WebSocket message."""
        if sent:
            self._ws_messages_sent += 1
        else:
            self._ws_messages_received += 1

    def record_error(self, error_type: str):
        """Record an error."""
        self._errors_total[error_type] = self._errors_total.get(error_type, 0) + 1

    def _normalize_path(self, path: str) -> str:
        """Normalize path by replacing IDs with placeholders."""
        parts = path.split("/")
        normalized = []
        for _i, part in enumerate(parts):
            # Check if this looks like a UUID or ID
            if len(part) > 20 or (len(part) == 36 and "-" in part):
                normalized.append("{id}")
            else:
                normalized.append(part)
        return "/".join(normalized)

    def get_metrics(self) -> str:
        """Generate Prometheus text format metrics."""
        lines = []

        # Uptime
        uptime = time.time() - self._start_time
        lines.append(f"# HELP {self.namespace}_uptime_seconds Time since service start")
        lines.append(f"# TYPE {self.namespace}_uptime_seconds gauge")
        lines.append(f"{self.namespace}_uptime_seconds {uptime:.2f}")
        lines.append("")

        # Request count
        lines.append(f"# HELP {self.namespace}_http_requests_total Total HTTP requests")
        lines.append(f"# TYPE {self.namespace}_http_requests_total counter")
        for key, count in self._request_count.items():
            parts = key.rsplit("_", 2)
            if len(parts) == 3:
                method, path, status = parts[0], parts[1], parts[2]
                lines.append(
                    f'{self.namespace}_http_requests_total{{method="{method}",'
                    f'path="{path}",status="{status}"}} {count}'
                )
        lines.append("")

        # Request latency
        lines.append(f"# HELP {self.namespace}_http_request_duration_seconds HTTP request latency")
        lines.append(f"# TYPE {self.namespace}_http_request_duration_seconds summary")
        for key, total in self._request_latency_sum.items():
            parts = key.split("_", 1)
            if len(parts) == 2:
                method, path = parts
                count = self._request_latency_count.get(key, 1)
                total / count if count > 0 else 0
                lines.append(
                    f'{self.namespace}_http_request_duration_seconds_sum{{method="{method}",'
                    f'path="{path}"}} {total:.6f}'
                )
                lines.append(
                    f'{self.namespace}_http_request_duration_seconds_count{{method="{method}",'
                    f'path="{path}"}} {count}'
                )
        lines.append("")

        # Job metrics
        lines.append(f"# HELP {self.namespace}_jobs_total Total optimization jobs")
        lines.append(f"# TYPE {self.namespace}_jobs_total counter")
        for key, count in self._jobs_total.items():
            parts = key.rsplit("_", 1)
            if len(parts) == 2:
                problem_type, status = parts
                lines.append(
                    f'{self.namespace}_jobs_total{{problem_type="{problem_type}",'
                    f'status="{status}"}} {count}'
                )
        lines.append("")

        lines.append(f"# HELP {self.namespace}_jobs_in_progress Current jobs in progress")
        lines.append(f"# TYPE {self.namespace}_jobs_in_progress gauge")
        for problem_type, count in self._jobs_in_progress.items():
            lines.append(
                f'{self.namespace}_jobs_in_progress{{problem_type="{problem_type}"}} {count}'
            )
        lines.append("")

        lines.append(f"# HELP {self.namespace}_job_duration_seconds Job processing duration")
        lines.append(f"# TYPE {self.namespace}_job_duration_seconds summary")
        for problem_type, total in self._jobs_duration_sum.items():
            count = self._jobs_duration_count.get(problem_type, 1)
            lines.append(
                f'{self.namespace}_job_duration_seconds_sum{{problem_type="{problem_type}"}} {total:.6f}'
            )
            lines.append(
                f'{self.namespace}_job_duration_seconds_count{{problem_type="{problem_type}"}} {count}'
            )
        lines.append("")

        # PQC metrics
        lines.append(f"# HELP {self.namespace}_pqc_operations_total Total PQC operations")
        lines.append(f"# TYPE {self.namespace}_pqc_operations_total counter")
        for key, count in self._pqc_operations.items():
            parts = key.rsplit("_", 1)
            if len(parts) == 2:
                operation, level = parts
                lines.append(
                    f'{self.namespace}_pqc_operations_total{{operation="{operation}",'
                    f'security_level="{level}"}} {count}'
                )
        lines.append("")

        lines.append(
            f"# HELP {self.namespace}_pqc_operation_duration_seconds PQC operation latency"
        )
        lines.append(f"# TYPE {self.namespace}_pqc_operation_duration_seconds summary")
        for operation, total in self._pqc_latency_sum.items():
            count = self._pqc_latency_count.get(operation, 1)
            lines.append(
                f'{self.namespace}_pqc_operation_duration_seconds_sum{{operation="{operation}"}} {total:.6f}'
            )
            lines.append(
                f'{self.namespace}_pqc_operation_duration_seconds_count{{operation="{operation}"}} {count}'
            )
        lines.append("")

        # WebSocket metrics
        lines.append(
            f"# HELP {self.namespace}_websocket_connections_total Total WebSocket connections"
        )
        lines.append(f"# TYPE {self.namespace}_websocket_connections_total counter")
        lines.append(f"{self.namespace}_websocket_connections_total {self._ws_connections_total}")
        lines.append("")

        lines.append(
            f"# HELP {self.namespace}_websocket_connections_active Active WebSocket connections"
        )
        lines.append(f"# TYPE {self.namespace}_websocket_connections_active gauge")
        lines.append(f"{self.namespace}_websocket_connections_active {self._ws_connections_active}")
        lines.append("")

        lines.append(f"# HELP {self.namespace}_websocket_messages_total Total WebSocket messages")
        lines.append(f"# TYPE {self.namespace}_websocket_messages_total counter")
        lines.append(
            f'{self.namespace}_websocket_messages_total{{direction="sent"}} {self._ws_messages_sent}'
        )
        lines.append(
            f'{self.namespace}_websocket_messages_total{{direction="received"}} {self._ws_messages_received}'
        )
        lines.append("")

        # Error metrics
        lines.append(f"# HELP {self.namespace}_errors_total Total errors by type")
        lines.append(f"# TYPE {self.namespace}_errors_total counter")
        for error_type, count in self._errors_total.items():
            lines.append(f'{self.namespace}_errors_total{{type="{error_type}"}} {count}')
        lines.append("")

        return "\n".join(lines)


# Global metrics instance
metrics = PrometheusMetrics()


class MetricsMiddleware(BaseHTTPMiddleware):
    """Middleware to collect HTTP request metrics."""

    # Paths to exclude from metrics
    EXCLUDE_PATHS = {"/metrics", "/health", "/health/live"}

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        # Skip excluded paths
        if request.url.path in self.EXCLUDE_PATHS:
            return await call_next(request)

        start_time = time.time()

        try:
            response = await call_next(request)
            duration = time.time() - start_time

            metrics.record_request(
                method=request.method,
                path=request.url.path,
                status_code=response.status_code,
                duration_seconds=duration,
            )

            return response

        except Exception as e:
            duration = time.time() - start_time
            metrics.record_request(
                method=request.method,
                path=request.url.path,
                status_code=500,
                duration_seconds=duration,
            )
            metrics.record_error(type(e).__name__)
            raise


def track_pqc_operation(operation: str, security_level: int = 3):
    """Decorator to track PQC operation metrics."""

    def decorator(func: Callable):
        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            start = time.time()
            try:
                result = func(*args, **kwargs)
                duration = time.time() - start
                metrics.record_pqc_operation(operation, security_level, duration)
                return result
            except Exception:
                metrics.record_error(f"pqc_{operation}")
                raise

        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            start = time.time()
            try:
                result = await func(*args, **kwargs)
                duration = time.time() - start
                metrics.record_pqc_operation(operation, security_level, duration)
                return result
            except Exception:
                metrics.record_error(f"pqc_{operation}")
                raise

        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        return sync_wrapper

    return decorator


@router.get("/metrics", response_class=PlainTextResponse)
async def prometheus_metrics():
    """
    Prometheus metrics endpoint.

    Returns metrics in Prometheus text exposition format.
    Configure Prometheus to scrape this endpoint.
    """
    return metrics.get_metrics()


@router.get("/metrics/json")
async def metrics_json() -> dict[str, Any]:
    """
    JSON metrics endpoint for debugging.

    Returns metrics in JSON format for easier inspection.
    """
    return {
        "uptime_seconds": time.time() - metrics._start_time,
        "requests": {
            "total": sum(metrics._request_count.values()),
            "by_endpoint": dict(metrics._request_count),
        },
        "jobs": {
            "total": sum(metrics._jobs_total.values()),
            "in_progress": sum(metrics._jobs_in_progress.values()),
            "by_type": dict(metrics._jobs_total),
        },
        "pqc_operations": {
            "total": sum(metrics._pqc_operations.values()),
            "by_operation": dict(metrics._pqc_operations),
        },
        "websocket": {
            "connections_total": metrics._ws_connections_total,
            "connections_active": metrics._ws_connections_active,
            "messages_sent": metrics._ws_messages_sent,
            "messages_received": metrics._ws_messages_received,
        },
        "errors": dict(metrics._errors_total),
    }
