"""
OpenTelemetry tracing configuration.

Provides distributed tracing for observability.
"""

import logging
import os
from contextlib import contextmanager
from typing import Any, Callable

from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter
from opentelemetry.trace.propagation.tracecontext import TraceContextTextMapPropagator

logger = logging.getLogger(__name__)

OTEL_ENABLED = os.getenv("OTEL_ENABLED", "false").lower() == "true"
OTEL_EXPORTER_ENDPOINT = os.getenv("OTEL_EXPORTER_ENDPOINT", "http://localhost:4317")
OTEL_SERVICE_NAME = os.getenv("OTEL_SERVICE_NAME", "qsop-api")

_tracer: trace.Tracer | None = None
_propagator = TraceContextTextMapPropagator()


def init_tracing() -> trace.Tracer | None:
    """Initialize OpenTelemetry tracing."""
    global _tracer

    if not OTEL_ENABLED:
        logger.info("OpenTelemetry tracing disabled")
        return None

    try:
        resource = Resource.create(
            {
                "service.name": OTEL_SERVICE_NAME,
                "service.version": os.getenv("APP_VERSION", "0.1.0"),
                "deployment.environment": os.getenv("APP_ENV", "development"),
            }
        )

        provider = TracerProvider(resource=resource)

        if OTEL_EXPORTER_ENDPOINT:
            otlp_exporter = OTLPSpanExporter(endpoint=OTEL_EXPORTER_ENDPOINT)
            provider.add_span_processor(BatchSpanProcessor(otlp_exporter))
        else:
            provider.add_span_processor(BatchSpanProcessor(ConsoleSpanExporter()))

        trace.set_tracer_provider(provider)
        _tracer = trace.get_tracer(OTEL_SERVICE_NAME)

        logger.info(f"OpenTelemetry tracing initialized: {OTEL_SERVICE_NAME}")
        return _tracer

    except Exception as e:
        logger.error(f"Failed to initialize tracing: {e}")
        return None


def get_tracer() -> trace.Tracer:
    """Get the tracer instance."""
    global _tracer
    if _tracer is None:
        _tracer = trace.get_tracer(OTEL_SERVICE_NAME)
    return _tracer


def get_trace_context() -> dict[str, str]:
    """Get current trace context for propagation."""
    from opentelemetry.context import Context

    context = Context()
    carrier: dict[str, str] = {}
    _propagator.inject(carrier, context)
    return carrier


def set_trace_context(carrier: dict[str, str]) -> None:
    """Set trace context from carrier."""
    context = _propagator.extract(carrier)
    from opentelemetry.context import attach, detach

    token = attach(context)
    return token


@contextmanager
def span(
    name: str,
    attributes: dict[str, Any] | None = None,
    kind: trace.SpanKind = trace.SpanKind.INTERNAL,
):
    """Context manager for creating spans."""
    if not OTEL_ENABLED:
        yield None
        return

    tracer = get_tracer()
    with tracer.start_as_current_span(name, kind=kind) as span:
        if attributes:
            for key, value in attributes.items():
                span.set_attribute(key, value)
        yield span


def traced(
    name: str | None = None,
    attributes: dict[str, Any] | None = None,
):
    """Decorator for tracing functions."""

    def decorator(func: Callable) -> Callable:
        span_name = name or func.__name__

        def wrapper(*args, **kwargs):
            if not OTEL_ENABLED:
                return func(*args, **kwargs)

            tracer = get_tracer()
            with tracer.start_as_current_span(span_name) as span:
                if attributes:
                    for key, value in attributes.items():
                        span.set_attribute(key, value)

                span.set_attribute("function.name", func.__name__)
                span.set_attribute("function.module", func.__module__)

                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    span.record_exception(e)
                    span.set_status(trace.Status(trace.StatusCode.ERROR, str(e)))
                    raise

        return wrapper

    return decorator


class TracingMiddleware:
    """FastAPI middleware for tracing requests."""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if not OTEL_ENABLED or scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        tracer = get_tracer()

        method = scope.get("method", "UNKNOWN")
        path = scope.get("path", "/")
        route = scope.get("route", {}).path if scope.get("route") else path

        with tracer.start_as_current_span(
            f"HTTP {method} {route}",
            kind=trace.SpanKind.SERVER,
        ) as span:
            span.set_attribute("http.method", method)
            span.set_attribute("http.url", path)
            span.set_attribute("http.scheme", scope.get("scheme", "http"))
            span.set_attribute("http.host", scope.get("server", ("localhost", 8000))[0])

            async def send_wrapper(message):
                if message["type"] == "http.response.start":
                    span.set_attribute("http.status_code", message["status"])
                await send(message)

            await self.app(scope, receive, send_wrapper)


def record_exception(span: trace.Span, exception: Exception) -> None:
    """Record an exception in a span."""
    if span:
        span.record_exception(exception)
        span.set_status(trace.Status(trace.StatusCode.ERROR, str(exception)))


def add_event(name: str, attributes: dict[str, Any] | None = None) -> None:
    """Add an event to the current span."""
    current_span = trace.get_current_span()
    if current_span:
        current_span.add_event(name, attributes or {})
