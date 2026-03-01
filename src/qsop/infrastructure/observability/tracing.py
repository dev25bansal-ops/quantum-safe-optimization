"""
Distributed tracing using OpenTelemetry.

Provides request tracing across services.
"""

from __future__ import annotations

import logging
from collections.abc import Generator
from contextlib import contextmanager
from typing import Any

logger = logging.getLogger(__name__)


def configure_tracing(
    service_name: str = "qsop",
    otlp_endpoint: str | None = None,
    sampling_ratio: float = 1.0,
) -> None:
    """
    Configure OpenTelemetry tracing.

    Args:
        service_name: Name of the service for traces
        otlp_endpoint: OTLP collector endpoint
        sampling_ratio: Trace sampling ratio (0.0 to 1.0)
    """
    try:
        from opentelemetry import trace
        from opentelemetry.sdk.resources import Resource
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.sampling import TraceIdRatioBased

        # Create resource
        resource = Resource.create(
            {
                "service.name": service_name,
            }
        )

        # Create tracer provider
        provider = TracerProvider(
            resource=resource,
            sampler=TraceIdRatioBased(sampling_ratio),
        )

        # Configure exporter
        if otlp_endpoint:
            try:
                from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
                from opentelemetry.sdk.trace.export import BatchSpanProcessor

                exporter = OTLPSpanExporter(endpoint=otlp_endpoint)
                provider.add_span_processor(BatchSpanProcessor(exporter))
            except ImportError:
                logger.warning("OTLP exporter not available")

        trace.set_tracer_provider(provider)

        logger.info(f"Tracing configured for {service_name}")

    except ImportError:
        logger.warning("OpenTelemetry not installed. Tracing disabled.")


def get_tracer(name: str) -> Any:
    """Get a tracer instance."""
    try:
        from opentelemetry import trace

        return trace.get_tracer(name)
    except ImportError:
        return NoOpTracer()


class NoOpTracer:
    """No-op tracer when OpenTelemetry is not available."""

    @contextmanager
    def start_as_current_span(
        self,
        name: str,
        **kwargs: Any,
    ) -> Generator[NoOpSpan, None, None]:
        yield NoOpSpan()

    def start_span(self, name: str, **kwargs: Any) -> NoOpSpan:
        return NoOpSpan()


class NoOpSpan:
    """No-op span."""

    def set_attribute(self, key: str, value: Any) -> None:
        pass

    def set_status(self, status: Any) -> None:
        pass

    def record_exception(self, exception: Exception) -> None:
        pass

    def end(self) -> None:
        pass

    def __enter__(self) -> NoOpSpan:
        return self

    def __exit__(self, *args: Any) -> None:
        pass


@contextmanager
def traced_operation(
    tracer: Any,
    operation_name: str,
    attributes: dict[str, Any] | None = None,
) -> Generator[Any, None, None]:
    """
    Context manager for tracing an operation.

    Args:
        tracer: The tracer to use
        operation_name: Name of the operation
        attributes: Optional span attributes
    """
    with tracer.start_as_current_span(operation_name) as span:
        if attributes:
            for key, value in attributes.items():
                span.set_attribute(key, value)

        try:
            yield span
        except Exception as e:
            span.record_exception(e)
            raise
