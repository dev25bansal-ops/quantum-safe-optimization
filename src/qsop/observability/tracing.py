"""Distributed tracing for quantum operations."""

from __future__ import annotations

import functools
import os
from contextlib import contextmanager
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Callable, TypeVar

if TYPE_CHECKING:
    from collections.abc import Iterator

try:
    from opentelemetry import trace
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import BatchSpanProcessor
    from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
    from opentelemetry.sdk.resources import Resource

    OTEL_AVAILABLE = True
except ImportError:
    OTEL_AVAILABLE = False

F = TypeVar("F", bound=Callable[..., Any])


@dataclass
class TracingConfig:
    """Configuration for distributed tracing."""

    service_name: str = "qsop"
    service_version: str = "0.2.0"
    environment: str = "production"
    otlp_endpoint: str | None = None
    sample_rate: float = 1.0
    enabled: bool = True


_tracer_provider: TracerProvider | None = None
_tracer: trace.Tracer | None = None


def setup_tracing(config: TracingConfig | None = None) -> trace.Tracer | None:
    """Setup distributed tracing.

    Args:
        config: Tracing configuration

    Returns:
        Tracer instance or None if not available
    """
    global _tracer_provider, _tracer

    if not OTEL_AVAILABLE:
        return None

    if config is None:
        config = TracingConfig(
            enabled=os.getenv("OTEL_ENABLED", "false").lower() == "true",
            otlp_endpoint=os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT"),
            environment=os.getenv("ENVIRONMENT", "production"),
        )

    if not config.enabled:
        return None

    resource = Resource.create(
        {
            "service.name": config.service_name,
            "service.version": config.service_version,
            "deployment.environment": config.environment,
        }
    )

    _tracer_provider = TracerProvider(resource=resource)

    if config.otlp_endpoint:
        otlp_exporter = OTLPSpanExporter(endpoint=config.otlp_endpoint)
        span_processor = BatchSpanProcessor(otlp_exporter)
        _tracer_provider.add_span_processor(span_processor)

    trace.set_tracer_provider(_tracer_provider)
    _tracer = trace.get_tracer(config.service_name, config.service_version)

    return _tracer


def get_tracer() -> trace.Tracer | None:
    """Get the tracer instance."""
    global _tracer
    if _tracer is None:
        _tracer = setup_tracing()
    return _tracer


@contextmanager
def trace_quantum_job(
    algorithm: str,
    backend: str,
    job_id: str,
    tenant_id: str | None = None,
) -> Iterator[trace.Span | None]:
    """Context manager for tracing quantum job execution.

    Args:
        algorithm: Algorithm name
        backend: Backend name
        job_id: Job identifier
        tenant_id: Tenant identifier

    Yields:
        Span or None if tracing disabled
    """
    tracer = get_tracer()

    if tracer is None:
        yield None
        return

    with tracer.start_as_current_span(
        "quantum_job.execute",
        attributes={
            "algorithm": algorithm,
            "backend": backend,
            "job.id": job_id,
            "tenant.id": tenant_id or "unknown",
        },
    ) as span:
        yield span


def trace_method(
    name: str | None = None,
    attributes: dict[str, Any] | None = None,
) -> Callable[[F], F]:
    """Decorator to trace a method.

    Args:
        name: Span name (defaults to method name)
        attributes: Static attributes to add

    Returns:
        Decorated function
    """

    def decorator(func: F) -> F:
        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            tracer = get_tracer()

            if tracer is None:
                return func(*args, **kwargs)

            span_name = name or f"{func.__module__}.{func.__name__}"

            with tracer.start_as_current_span(span_name) as span:
                if attributes:
                    for key, value in attributes.items():
                        span.set_attribute(key, value)

                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    span.record_exception(e)
                    span.set_status(trace.Status(trace.StatusCode.ERROR, str(e)))
                    raise

        return wrapper  # type: ignore

    return decorator


def add_span_attributes(attributes: dict[str, Any]) -> None:
    """Add attributes to current span.

    Args:
        attributes: Attributes to add
    """
    if not OTEL_AVAILABLE:
        return

    span = trace.get_current_span()
    if span and span.is_recording():
        for key, value in attributes.items():
            span.set_attribute(key, value)


def record_exception(exception: Exception) -> None:
    """Record exception on current span.

    Args:
        exception: Exception to record
    """
    if not OTEL_AVAILABLE:
        return

    span = trace.get_current_span()
    if span and span.is_recording():
        span.record_exception(exception)
        span.set_status(trace.Status(trace.StatusCode.ERROR, str(exception)))


__all__ = [
    "TracingConfig",
    "setup_tracing",
    "get_tracer",
    "trace_quantum_job",
    "trace_method",
    "add_span_attributes",
    "record_exception",
]
