"""
OpenTelemetry Tracing Configuration for Quantum-Safe Optimization Platform

Provides distributed tracing across API, optimization, and backend services.
"""

import os
from contextlib import contextmanager
from functools import wraps
from typing import Any, Callable, Generator, TypeVar

from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor
from opentelemetry.instrumentation.redis import RedisInstrumentor
from opentelemetry.propagate import set_global_textmap
from opentelemetry.sdk.resources import Resource, SERVICE_NAME, SERVICE_VERSION
from opentelemetry.sdk.trace import TracerProvider, SpanProcessor
from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter
from opentelemetry.sdk.trace.sampling import (
    ParentBasedTraceIdRatio,
    TraceIdRatioBased,
    ALWAYS_ON,
)
from opentelemetry.trace import Status, StatusCode, Span
from opentelemetry.trace.propagation.tracecontext import TraceContextTextMapPropagator


# Type variable for decorated functions
F = TypeVar("F", bound=Callable[..., Any])


class TelemetryConfig:
    """Configuration for OpenTelemetry setup."""
    
    def __init__(
        self,
        service_name: str = "quantum-api",
        service_version: str = "1.0.0",
        environment: str = "development",
        otlp_endpoint: str | None = None,
        sample_rate: float = 1.0,
        console_export: bool = False,
    ):
        self.service_name = service_name
        self.service_version = service_version
        self.environment = environment
        self.otlp_endpoint = otlp_endpoint or os.getenv(
            "OTEL_EXPORTER_OTLP_ENDPOINT", "http://localhost:4317"
        )
        self.sample_rate = sample_rate
        self.console_export = console_export


def setup_telemetry(config: TelemetryConfig | None = None) -> TracerProvider:
    """
    Initialize OpenTelemetry tracing with the provided configuration.
    
    Args:
        config: TelemetryConfig instance with tracing settings
        
    Returns:
        Configured TracerProvider
    """
    if config is None:
        config = TelemetryConfig(
            service_name=os.getenv("OTEL_SERVICE_NAME", "quantum-api"),
            service_version=os.getenv("SERVICE_VERSION", "1.0.0"),
            environment=os.getenv("APP_ENV", "development"),
            otlp_endpoint=os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT"),
            sample_rate=float(os.getenv("OTEL_TRACES_SAMPLER_ARG", "1.0")),
            console_export=os.getenv("OTEL_CONSOLE_EXPORT", "false").lower() == "true",
        )
    
    # Create resource with service information
    resource = Resource.create({
        SERVICE_NAME: config.service_name,
        SERVICE_VERSION: config.service_version,
        "deployment.environment": config.environment,
        "service.namespace": "quantum-platform",
    })
    
    # Configure sampler based on sample rate
    if config.sample_rate >= 1.0:
        sampler = ALWAYS_ON
    else:
        sampler = ParentBasedTraceIdRatio(config.sample_rate)
    
    # Create tracer provider
    provider = TracerProvider(
        resource=resource,
        sampler=sampler,
    )
    
    # Add OTLP exporter for production
    if config.otlp_endpoint and os.getenv("OTEL_ENABLED", "true").lower() == "true":
        otlp_exporter = OTLPSpanExporter(
            endpoint=config.otlp_endpoint,
            insecure=config.environment != "production",
        )
        provider.add_span_processor(BatchSpanProcessor(otlp_exporter))
    
    # Add console exporter for development/debugging
    if config.console_export:
        console_exporter = ConsoleSpanExporter()
        provider.add_span_processor(BatchSpanProcessor(console_exporter))
    
    # Set as global tracer provider
    trace.set_tracer_provider(provider)
    
    # Set up context propagation (W3C Trace Context + B3 for compatibility)
    set_global_textmap(TraceContextTextMapPropagator())
    
    return provider


def instrument_fastapi(app) -> None:
    """
    Instrument FastAPI application with OpenTelemetry.
    
    Args:
        app: FastAPI application instance
    """
    FastAPIInstrumentor.instrument_app(
        app,
        excluded_urls="health,health/ready,health/live,metrics",
    )


def instrument_dependencies() -> None:
    """Instrument common dependencies (Redis, HTTP clients)."""
    # Instrument Redis
    RedisInstrumentor().instrument()
    
    # Instrument HTTPX client
    HTTPXClientInstrumentor().instrument()


def get_tracer(name: str = "quantum-api") -> trace.Tracer:
    """
    Get a tracer instance for creating spans.
    
    Args:
        name: Tracer name (typically module or component name)
        
    Returns:
        Tracer instance
    """
    return trace.get_tracer(name)


@contextmanager
def create_span(
    name: str,
    tracer_name: str = "quantum-api",
    attributes: dict[str, Any] | None = None,
    kind: trace.SpanKind = trace.SpanKind.INTERNAL,
) -> Generator[Span, None, None]:
    """
    Context manager for creating traced spans.
    
    Args:
        name: Span name
        tracer_name: Name of the tracer to use
        attributes: Optional span attributes
        kind: Span kind (INTERNAL, SERVER, CLIENT, PRODUCER, CONSUMER)
        
    Yields:
        Active span
    """
    tracer = get_tracer(tracer_name)
    with tracer.start_as_current_span(
        name,
        kind=kind,
        attributes=attributes or {},
    ) as span:
        try:
            yield span
        except Exception as e:
            span.set_status(Status(StatusCode.ERROR, str(e)))
            span.record_exception(e)
            raise


def traced(
    name: str | None = None,
    tracer_name: str = "quantum-api",
    attributes: dict[str, Any] | None = None,
) -> Callable[[F], F]:
    """
    Decorator for tracing functions.
    
    Args:
        name: Optional span name (defaults to function name)
        tracer_name: Name of the tracer to use
        attributes: Optional span attributes
        
    Returns:
        Decorated function
    """
    def decorator(func: F) -> F:
        span_name = name or f"{func.__module__}.{func.__name__}"
        
        @wraps(func)
        async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
            tracer = get_tracer(tracer_name)
            with tracer.start_as_current_span(
                span_name,
                attributes=attributes or {},
            ) as span:
                try:
                    # Add function arguments as span attributes (excluding sensitive data)
                    span.set_attribute("function.name", func.__name__)
                    span.set_attribute("function.module", func.__module__)
                    return await func(*args, **kwargs)
                except Exception as e:
                    span.set_status(Status(StatusCode.ERROR, str(e)))
                    span.record_exception(e)
                    raise
        
        @wraps(func)
        def sync_wrapper(*args: Any, **kwargs: Any) -> Any:
            tracer = get_tracer(tracer_name)
            with tracer.start_as_current_span(
                span_name,
                attributes=attributes or {},
            ) as span:
                try:
                    span.set_attribute("function.name", func.__name__)
                    span.set_attribute("function.module", func.__module__)
                    return func(*args, **kwargs)
                except Exception as e:
                    span.set_status(Status(StatusCode.ERROR, str(e)))
                    span.record_exception(e)
                    raise
        
        import asyncio
        if asyncio.iscoroutinefunction(func):
            return async_wrapper  # type: ignore
        return sync_wrapper  # type: ignore
    
    return decorator


class OptimizationTracer:
    """
    Specialized tracer for optimization operations.
    
    Provides pre-configured tracing for QAOA, VQE, and annealing operations.
    """
    
    def __init__(self, tracer_name: str = "quantum-optimization"):
        self.tracer = get_tracer(tracer_name)
    
    @contextmanager
    def trace_optimization_job(
        self,
        job_id: str,
        algorithm: str,
        problem_type: str,
        **extra_attributes: Any,
    ) -> Generator[Span, None, None]:
        """
        Trace an optimization job execution.
        
        Args:
            job_id: Unique job identifier
            algorithm: Algorithm name (QAOA, VQE, ANNEALING)
            problem_type: Type of optimization problem
            **extra_attributes: Additional span attributes
        """
        attributes = {
            "optimization.job_id": job_id,
            "optimization.algorithm": algorithm,
            "optimization.problem_type": problem_type,
            **extra_attributes,
        }
        
        with self.tracer.start_as_current_span(
            f"optimization.{algorithm.lower()}",
            kind=trace.SpanKind.INTERNAL,
            attributes=attributes,
        ) as span:
            yield span
    
    @contextmanager
    def trace_iteration(
        self,
        iteration: int,
        total_iterations: int,
    ) -> Generator[Span, None, None]:
        """Trace a single optimization iteration."""
        with self.tracer.start_as_current_span(
            "optimization.iteration",
            attributes={
                "optimization.iteration": iteration,
                "optimization.total_iterations": total_iterations,
            },
        ) as span:
            yield span
    
    def record_result(
        self,
        span: Span,
        optimal_value: float,
        iterations_used: int,
        converged: bool,
    ) -> None:
        """Record optimization result metrics on the span."""
        span.set_attribute("optimization.result.optimal_value", optimal_value)
        span.set_attribute("optimization.result.iterations_used", iterations_used)
        span.set_attribute("optimization.result.converged", converged)


class CryptoTracer:
    """
    Specialized tracer for cryptographic operations.
    
    Traces PQC operations without exposing sensitive data.
    """
    
    def __init__(self, tracer_name: str = "quantum-crypto"):
        self.tracer = get_tracer(tracer_name)
    
    @contextmanager
    def trace_key_generation(
        self,
        algorithm: str,
        key_size: int | None = None,
    ) -> Generator[Span, None, None]:
        """Trace key generation operations."""
        with self.tracer.start_as_current_span(
            "crypto.key_generation",
            attributes={
                "crypto.algorithm": algorithm,
                "crypto.key_size": key_size or 0,
                "crypto.operation": "generate",
            },
        ) as span:
            yield span
    
    @contextmanager
    def trace_encryption(
        self,
        algorithm: str,
        data_size: int,
    ) -> Generator[Span, None, None]:
        """Trace encryption operations."""
        with self.tracer.start_as_current_span(
            "crypto.encrypt",
            attributes={
                "crypto.algorithm": algorithm,
                "crypto.data_size_bytes": data_size,
                "crypto.operation": "encrypt",
            },
        ) as span:
            yield span
    
    @contextmanager
    def trace_decryption(
        self,
        algorithm: str,
    ) -> Generator[Span, None, None]:
        """Trace decryption operations."""
        with self.tracer.start_as_current_span(
            "crypto.decrypt",
            attributes={
                "crypto.algorithm": algorithm,
                "crypto.operation": "decrypt",
            },
        ) as span:
            yield span
    
    @contextmanager
    def trace_signing(
        self,
        algorithm: str,
        message_size: int,
    ) -> Generator[Span, None, None]:
        """Trace signing operations."""
        with self.tracer.start_as_current_span(
            "crypto.sign",
            attributes={
                "crypto.algorithm": algorithm,
                "crypto.message_size_bytes": message_size,
                "crypto.operation": "sign",
            },
        ) as span:
            yield span
    
    @contextmanager
    def trace_verification(
        self,
        algorithm: str,
    ) -> Generator[Span, None, None]:
        """Trace signature verification operations."""
        with self.tracer.start_as_current_span(
            "crypto.verify",
            attributes={
                "crypto.algorithm": algorithm,
                "crypto.operation": "verify",
            },
        ) as span:
            yield span


def get_current_span() -> Span:
    """Get the currently active span."""
    return trace.get_current_span()


def add_span_attributes(**attributes: Any) -> None:
    """Add attributes to the current span."""
    span = get_current_span()
    for key, value in attributes.items():
        span.set_attribute(key, value)


def record_exception(exception: Exception) -> None:
    """Record an exception on the current span."""
    span = get_current_span()
    span.record_exception(exception)
    span.set_status(Status(StatusCode.ERROR, str(exception)))
