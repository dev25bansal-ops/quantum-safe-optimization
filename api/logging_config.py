"""
Structured Logging Configuration for Quantum-Safe Optimization Platform

Uses structlog for structured, context-rich logging with JSON output
for production and human-readable output for development.
"""

import logging
import sys
from typing import Any

import structlog
from structlog.types import Processor


def add_service_context(
    logger: logging.Logger, method_name: str, event_dict: dict[str, Any]
) -> dict[str, Any]:
    """Add service-level context to all log entries."""
    event_dict["service"] = "quantum-api"
    event_dict["version"] = "1.0.0"
    return event_dict


def add_caller_info(
    logger: logging.Logger, method_name: str, event_dict: dict[str, Any]
) -> dict[str, Any]:
    """Add caller information for debugging."""
    # structlog handles this automatically with CallsiteParameterAdder
    return event_dict


def setup_logging(
    log_level: str = "INFO",
    log_format: str = "json",
    service_name: str = "quantum-api",
) -> structlog.BoundLogger:
    """
    Configure structured logging for the application.
    
    Args:
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_format: Output format ('json' for production, 'console' for development)
        service_name: Name of the service for log context
        
    Returns:
        Configured structlog logger
    """
    # Determine if we're in development mode
    is_development = log_format.lower() == "console"
    
    # Shared processors for all environments
    shared_processors: list[Processor] = [
        # Add log level to event dict
        structlog.stdlib.add_log_level,
        # Add logger name
        structlog.stdlib.add_logger_name,
        # Add timestamp
        structlog.processors.TimeStamper(fmt="iso"),
        # Add caller information (file, line, function)
        structlog.processors.CallsiteParameterAdder(
            parameters=[
                structlog.processors.CallsiteParameter.FILENAME,
                structlog.processors.CallsiteParameter.LINENO,
                structlog.processors.CallsiteParameter.FUNC_NAME,
            ]
        ),
        # Process stack info for exceptions
        structlog.processors.StackInfoRenderer(),
        # Format exceptions
        structlog.processors.format_exc_info,
        # Filter by log level
        structlog.stdlib.filter_by_level,
    ]
    
    if is_development:
        # Development: Human-readable colored output
        processors = shared_processors + [
            structlog.stdlib.PositionalArgumentsFormatter(),
            structlog.processors.UnicodeDecoder(),
            structlog.dev.ConsoleRenderer(
                colors=True,
                exception_formatter=structlog.dev.rich_traceback,
            ),
        ]
    else:
        # Production: JSON output for log aggregation
        processors = shared_processors + [
            structlog.stdlib.PositionalArgumentsFormatter(),
            structlog.processors.UnicodeDecoder(),
            # Add service context
            structlog.processors.EventRenamer("message"),
            structlog.processors.JSONRenderer(),
        ]
    
    # Configure structlog
    structlog.configure(
        processors=processors,
        wrapper_class=structlog.stdlib.BoundLogger,
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )
    
    # Configure standard library logging
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=getattr(logging, log_level.upper()),
    )
    
    # Set log levels for noisy libraries
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    
    # Create and return the logger with service context
    logger = structlog.get_logger(service_name)
    return logger.bind(service=service_name)


def get_logger(name: str | None = None) -> structlog.BoundLogger:
    """
    Get a logger instance with optional name binding.
    
    Args:
        name: Optional name for the logger (e.g., module name)
        
    Returns:
        structlog BoundLogger instance
    """
    logger = structlog.get_logger()
    if name:
        return logger.bind(component=name)
    return logger


class LoggerMiddleware:
    """
    ASGI middleware for request/response logging.
    
    Logs incoming requests and outgoing responses with timing information.
    """
    
    def __init__(self, app, logger: structlog.BoundLogger | None = None):
        self.app = app
        self.logger = logger or get_logger("http")
    
    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        
        import time
        from uuid import uuid4
        
        # Generate request ID
        request_id = str(uuid4())
        start_time = time.perf_counter()
        
        # Extract request information
        method = scope.get("method", "UNKNOWN")
        path = scope.get("path", "/")
        query_string = scope.get("query_string", b"").decode()
        client = scope.get("client", ("unknown", 0))
        
        # Bind request context to logger
        request_logger = self.logger.bind(
            request_id=request_id,
            method=method,
            path=path,
            client_ip=client[0] if client else "unknown",
        )
        
        # Store logger in scope for access in route handlers
        scope["logger"] = request_logger
        scope["request_id"] = request_id
        
        # Log request
        request_logger.info(
            "request_started",
            query_string=query_string,
        )
        
        # Track response status
        response_status = 500  # Default to error
        
        async def send_wrapper(message):
            nonlocal response_status
            if message["type"] == "http.response.start":
                response_status = message.get("status", 500)
            await send(message)
        
        try:
            await self.app(scope, receive, send_wrapper)
        except Exception as e:
            request_logger.exception(
                "request_failed",
                error=str(e),
                error_type=type(e).__name__,
            )
            raise
        finally:
            # Calculate duration
            duration_ms = (time.perf_counter() - start_time) * 1000
            
            # Log response
            log_method = request_logger.info if response_status < 400 else request_logger.warning
            if response_status >= 500:
                log_method = request_logger.error
            
            log_method(
                "request_completed",
                status_code=response_status,
                duration_ms=round(duration_ms, 2),
            )


def log_optimization_event(
    logger: structlog.BoundLogger,
    event: str,
    job_id: str,
    algorithm: str | None = None,
    **kwargs: Any,
) -> None:
    """
    Log optimization-specific events with standard fields.
    
    Args:
        logger: structlog logger instance
        event: Event name
        job_id: Optimization job ID
        algorithm: Algorithm name (QAOA, VQE, etc.)
        **kwargs: Additional context
    """
    logger.info(
        event,
        job_id=job_id,
        algorithm=algorithm,
        category="optimization",
        **kwargs,
    )


def log_crypto_event(
    logger: structlog.BoundLogger,
    event: str,
    operation: str,
    **kwargs: Any,
) -> None:
    """
    Log cryptography-specific events with standard fields.
    
    Args:
        logger: structlog logger instance
        event: Event name
        operation: Crypto operation (encrypt, decrypt, sign, verify)
        **kwargs: Additional context
    """
    logger.info(
        event,
        operation=operation,
        category="crypto",
        **kwargs,
    )
