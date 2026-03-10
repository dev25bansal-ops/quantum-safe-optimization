"""Structured logging configuration for quantum optimization."""

from __future__ import annotations

import json
import logging
import os
import sys
from contextvars import ContextVar
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

context_correlation_id: ContextVar[str | None] = ContextVar("correlation_id", default=None)
context_tenant_id: ContextVar[str | None] = ContextVar("tenant_id", default=None)
context_job_id: ContextVar[str | None] = ContextVar("job_id", default=None)


@dataclass
class LoggingConfig:
    """Logging configuration."""

    level: str = "INFO"
    format: str = "json"
    include_timestamp: bool = True
    include_hostname: bool = True
    include_pid: bool = True
    include_context: bool = True


class StructuredFormatter(logging.Formatter):
    """JSON structured log formatter."""

    def __init__(
        self,
        include_timestamp: bool = True,
        include_hostname: bool = True,
        include_pid: bool = True,
        include_context: bool = True,
    ):
        super().__init__()
        self.include_timestamp = include_timestamp
        self.include_hostname = include_hostname
        self.include_pid = include_pid
        self.include_context = include_context

    def format(self, record: logging.LogRecord) -> str:
        """Format log record as JSON.

        Args:
            record: Log record

        Returns:
            JSON formatted string
        """
        log_obj: dict[str, Any] = {
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }

        if self.include_timestamp:
            log_obj["timestamp"] = datetime.now(timezone.utc).isoformat()

        if self.include_hostname:
            import socket

            log_obj["hostname"] = socket.gethostname()

        if self.include_pid:
            log_obj["pid"] = record.process

        if self.include_context:
            correlation_id = context_correlation_id.get()
            if correlation_id:
                log_obj["correlation_id"] = correlation_id

            tenant_id = context_tenant_id.get()
            if tenant_id:
                log_obj["tenant_id"] = tenant_id

            job_id = context_job_id.get()
            if job_id:
                log_obj["job_id"] = job_id

        if record.exc_info:
            log_obj["exception"] = self.formatException(record.exc_info)
            log_obj["exc_type"] = record.exc_info[0].__name__ if record.exc_info[0] else None

        if hasattr(record, "algorithm"):
            log_obj["algorithm"] = record.algorithm

        if hasattr(record, "backend"):
            log_obj["backend"] = record.backend

        if hasattr(record, "duration_ms"):
            log_obj["duration_ms"] = record.duration_ms

        if hasattr(record, "extra_data"):
            log_obj.update(record.extra_data)

        return json.dumps(log_obj, default=str)


class JobLogger:
    """Context-aware logger for quantum jobs."""

    def __init__(
        self,
        name: str,
        job_id: str,
        algorithm: str,
        backend: str,
        tenant_id: str | None = None,
    ):
        """Initialize job logger.

        Args:
            name: Logger name
            job_id: Job identifier
            algorithm: Algorithm name
            backend: Backend name
            tenant_id: Tenant identifier
        """
        self.logger = logging.getLogger(name)
        self.job_id = job_id
        self.algorithm = algorithm
        self.backend = backend
        self.tenant_id = tenant_id

        context_job_id.set(job_id)
        if tenant_id:
            context_tenant_id.set(tenant_id)

    def _log(self, level: int, msg: str, *args: Any, **kwargs: Any) -> None:
        """Log with job context.

        Args:
            level: Log level
            msg: Log message
            args: Format args
            kwargs: Extra kwargs
        """
        extra = kwargs.pop("extra", {})
        extra["algorithm"] = self.algorithm
        extra["backend"] = self.backend

        self.logger.log(level, msg, *args, extra=extra, **kwargs)

    def debug(self, msg: str, *args: Any, **kwargs: Any) -> None:
        self._log(logging.DEBUG, msg, *args, **kwargs)

    def info(self, msg: str, *args: Any, **kwargs: Any) -> None:
        self._log(logging.INFO, msg, *args, **kwargs)

    def warning(self, msg: str, *args: Any, **kwargs: Any) -> None:
        self._log(logging.WARNING, msg, *args, **kwargs)

    def error(self, msg: str, *args: Any, **kwargs: Any) -> None:
        self._log(logging.ERROR, msg, *args, **kwargs)

    def exception(self, msg: str, *args: Any, **kwargs: Any) -> None:
        extra = kwargs.pop("extra", {})
        extra["algorithm"] = self.algorithm
        extra["backend"] = self.backend

        self.logger.exception(msg, *args, extra=extra, **kwargs)

    def log_progress(
        self,
        iteration: int,
        max_iterations: int,
        current_value: float,
        best_value: float | None = None,
    ) -> None:
        """Log optimization progress.

        Args:
            iteration: Current iteration
            max_iterations: Total iterations
            current_value: Current objective value
            best_value: Best value found
        """
        extra_data = {
            "iteration": iteration,
            "max_iterations": max_iterations,
            "current_value": current_value,
            "progress_pct": iteration / max_iterations * 100,
        }

        if best_value is not None:
            extra_data["best_value"] = best_value

        self.info(
            f"Progress: {iteration}/{max_iterations} ({extra_data['progress_pct']:.1f}%)",
            extra={"extra_data": extra_data},
        )

    def log_metrics(self, metrics: dict[str, Any]) -> None:
        """Log job metrics.

        Args:
            metrics: Metrics dictionary
        """
        self.info(
            f"Metrics: {metrics}",
            extra={"extra_data": metrics},
        )

    def log_circuit_info(
        self,
        depth: int,
        width: int,
        gate_count: int,
        two_qubit_gates: int,
    ) -> None:
        """Log circuit information.

        Args:
            depth: Circuit depth
            width: Number of qubits
            gate_count: Total gates
            two_qubit_gates: Two-qubit gate count
        """
        self.info(
            f"Circuit: depth={depth}, width={width}, gates={gate_count}, "
            f"2q_gates={two_qubit_gates}",
            extra={
                "extra_data": {
                    "circuit_depth": depth,
                    "circuit_width": width,
                    "gate_count": gate_count,
                    "two_qubit_gates": two_qubit_gates,
                }
            },
        )


def setup_logging(config: LoggingConfig | None = None) -> None:
    """Setup structured logging.

    Args:
        config: Logging configuration
    """
    if config is None:
        config = LoggingConfig(
            level=os.getenv("LOG_LEVEL", "INFO"),
            format=os.getenv("LOG_FORMAT", "json"),
        )

    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, config.level.upper()))

    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)

    handler = logging.StreamHandler(sys.stdout)

    if config.format == "json":
        formatter = StructuredFormatter(
            include_timestamp=config.include_timestamp,
            include_hostname=config.include_hostname,
            include_pid=config.include_pid,
            include_context=config.include_context,
        )
    else:
        formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")

    handler.setFormatter(formatter)
    root_logger.addHandler(handler)

    logging.getLogger("uvicorn").setLevel(logging.WARNING)
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)


def get_logger(name: str) -> logging.Logger:
    """Get a logger instance.

    Args:
        name: Logger name

    Returns:
        Logger instance
    """
    return logging.getLogger(name)


def set_correlation_id(correlation_id: str) -> None:
    """Set correlation ID for request tracking.

    Args:
        correlation_id: Correlation ID
    """
    context_correlation_id.set(correlation_id)


def set_tenant_context(tenant_id: str) -> None:
    """Set tenant context.

    Args:
        tenant_id: Tenant identifier
    """
    context_tenant_id.set(tenant_id)


__all__ = [
    "LoggingConfig",
    "JobLogger",
    "setup_logging",
    "get_logger",
    "set_correlation_id",
    "set_tenant_context",
]
