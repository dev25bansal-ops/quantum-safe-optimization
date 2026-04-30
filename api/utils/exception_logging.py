"""
Enhanced Exception Handler with Structured Logging.

Provides proper logging for exception handlers throughout the application.
"""

import logging
import traceback
from functools import wraps
from typing import Any, Callable, Optional

import structlog

logger = structlog.get_logger()


def log_exception(
    operation: str,
    include_traceback: bool = True,
    reraise: bool = False,
    default_return: Any = None,
):
    """
    Decorator to add structured logging to exception handlers.

    Args:
        operation: Name of the operation being performed
        include_traceback: Whether to include traceback in logs
        reraise: Whether to re-raise the exception
        default_return: Value to return if exception is caught

    Example:
        @log_exception("database_query", include_traceback=True)
        async def query_database(query: str):
            ...
    """

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            try:
                return await func(*args, **kwargs)
            except Exception as e:
                log_data = {
                    "operation": operation,
                    "function": func.__name__,
                    "error_type": type(e).__name__,
                    "error_message": str(e),
                }

                if include_traceback:
                    log_data["traceback"] = traceback.format_exc()

                logger.error("operation_failed", **log_data)

                if reraise:
                    raise
                return default_return

        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                log_data = {
                    "operation": operation,
                    "function": func.__name__,
                    "error_type": type(e).__name__,
                    "error_message": str(e),
                }

                if include_traceback:
                    log_data["traceback"] = traceback.format_exc()

                logger.error("operation_failed", **log_data)

                if reraise:
                    raise
                return default_return

        import asyncio

        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        return sync_wrapper

    return decorator


class ExceptionLogger:
    """
    Context manager for exception logging.

    Example:
        async with ExceptionLogger("database_operation", reraise=False):
            await execute_query()
    """

    def __init__(
        self,
        operation: str,
        reraise: bool = False,
        default_return: Any = None,
        extra_context: Optional[dict] = None,
    ):
        self.operation = operation
        self.reraise = reraise
        self.default_return = default_return
        self.extra_context = extra_context or {}

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if exc_type is not None:
            log_data = {
                "operation": self.operation,
                "error_type": exc_type.__name__,
                "error_message": str(exc_val),
                "traceback": "".join(traceback.format_tb(exc_tb)),
                **self.extra_context,
            }

            logger.error("operation_failed", **log_data)

            if self.reraise:
                return False
            return True
        return False

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type is not None:
            log_data = {
                "operation": self.operation,
                "error_type": exc_type.__name__,
                "error_message": str(exc_val),
                "traceback": "".join(traceback.format_tb(exc_tb)),
                **self.extra_context,
            }

            logger.error("operation_failed", **log_data)

            if self.reraise:
                return False
            return True
        return False


def safe_pass_with_log(operation: str, context: Optional[dict] = None):
    """
    Replace bare `pass` statements with logged exception handling.

    Example:
        try:
            risky_operation()
        except Exception:
            safe_pass_with_log("risky_operation", {"input": data})
    """
    logger.warning("exception_silently_handled", operation=operation, context=context or {})


class LoggedExceptionHandler:
    """
    Global exception handler for consistent logging.

    Usage:
        handler = LoggedExceptionHandler()

        try:
            ...
        except Exception as e:
            handler.handle(e, "operation_name", {"context": "data"})
    """

    def __init__(self, include_traceback: bool = True):
        self.include_traceback = include_traceback
        self._counts: dict[str, int] = {}

    def handle(
        self,
        exception: Exception,
        operation: str,
        context: Optional[dict] = None,
        reraise: bool = False,
    ) -> None:
        """Handle and log an exception."""
        error_type = type(exception).__name__

        self._counts[f"{operation}:{error_type}"] = (
            self._counts.get(f"{operation}:{error_type}", 0) + 1
        )

        log_data = {
            "operation": operation,
            "error_type": error_type,
            "error_message": str(exception),
            "occurrence_count": self._counts[f"{operation}:{error_type}"],
            **(context or {}),
        }

        if self.include_traceback:
            log_data["traceback"] = traceback.format_exc()

        logger.error("exception_handled", **log_data)

        if reraise:
            raise exception

    def get_stats(self) -> dict:
        """Get exception statistics."""
        return {"total_exceptions": sum(self._counts.values()), "by_type": dict(self._counts)}


exception_handler = LoggedExceptionHandler()
