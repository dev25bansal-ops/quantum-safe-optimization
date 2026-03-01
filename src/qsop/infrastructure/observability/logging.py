"""
Structured logging configuration.

Provides consistent, structured logging across the platform.
"""

from __future__ import annotations

import logging
import sys
from typing import Any

import structlog


def configure_logging(
    level: str = "INFO",
    format: str = "json",
    service_name: str = "qsop",
) -> None:
    """
    Configure structured logging.

    Args:
        level: Log level (DEBUG, INFO, WARNING, ERROR)
        format: Output format (json, console)
        service_name: Service name for log context
    """
    # Configure standard logging
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=getattr(logging, level.upper()),
    )

    # Processors for structlog
    processors = [
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.stdlib.add_logger_name,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.UnicodeDecoder(),
    ]

    if format == "json":
        processors.append(structlog.processors.JSONRenderer())
    else:
        processors.append(structlog.dev.ConsoleRenderer(colors=True))

    structlog.configure(
        processors=processors,
        wrapper_class=structlog.stdlib.BoundLogger,
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )

    # Add service name to context
    structlog.contextvars.bind_contextvars(service=service_name)


def get_logger(name: str) -> structlog.stdlib.BoundLogger:
    """Get a structured logger."""
    return structlog.get_logger(name)


class SecureLogger:
    """
    Logger that redacts sensitive data.

    Automatically redacts known sensitive fields from log output.
    """

    SENSITIVE_FIELDS = {
        "password",
        "secret",
        "token",
        "api_key",
        "private_key",
        "credential",
        "authorization",
    }

    def __init__(self, name: str):
        self._logger = get_logger(name)

    def _redact(self, data: Any) -> Any:
        """Recursively redact sensitive fields."""
        if isinstance(data, dict):
            return {
                k: "[REDACTED]" if self._is_sensitive(k) else self._redact(v)
                for k, v in data.items()
            }
        elif isinstance(data, list):
            return [self._redact(item) for item in data]
        return data

    def _is_sensitive(self, key: str) -> bool:
        """Check if a key name indicates sensitive data."""
        key_lower = key.lower()
        return any(s in key_lower for s in self.SENSITIVE_FIELDS)

    def info(self, msg: str, **kwargs: Any) -> None:
        """Log info with redaction."""
        self._logger.info(msg, **self._redact(kwargs))

    def debug(self, msg: str, **kwargs: Any) -> None:
        """Log debug with redaction."""
        self._logger.debug(msg, **self._redact(kwargs))

    def warning(self, msg: str, **kwargs: Any) -> None:
        """Log warning with redaction."""
        self._logger.warning(msg, **self._redact(kwargs))

    def error(self, msg: str, **kwargs: Any) -> None:
        """Log error with redaction."""
        self._logger.error(msg, **self._redact(kwargs))

    def bind(self, **kwargs: Any) -> SecureLogger:
        """Bind context to logger."""
        new_logger = SecureLogger(self._logger.name)
        new_logger._logger = self._logger.bind(**self._redact(kwargs))
        return new_logger
