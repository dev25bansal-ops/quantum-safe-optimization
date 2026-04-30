"""
Secure Demo Mode Configuration.

Provides safe demo mode functionality with environment validation,
explicit warnings, and audit logging.
"""

import os
import logging
from functools import wraps
from typing import Any, Callable

logger = logging.getLogger(__name__)

PRODUCTION_ENVIRONMENTS = {"production", "prod", "live"}
DEVELOPMENT_ENVIRONMENTS = {"development", "dev", "local", "test", "testing"}

_current_env = os.getenv("ENVIRONMENT", "development").lower()
_demo_mode_requested = os.getenv("DEMO_MODE", "false").lower() == "true"
_force_demo = os.getenv("FORCE_DEMO_MODE", "false").lower() == "true"


def is_production_environment() -> bool:
    """Check if running in production environment."""
    return _current_env in PRODUCTION_ENVIRONMENTS


def is_development_environment() -> bool:
    """Check if running in development environment."""
    return _current_env in DEVELOPMENT_ENVIRONMENTS


def is_demo_mode_allowed() -> bool:
    """
    Determine if demo mode is allowed in current environment.

    Demo mode is ONLY allowed in:
    - Development environments (dev, local, test)
    - When explicitly forced (for CI/CD testing only)

    Returns:
        True if demo mode can be safely enabled
    """
    if _force_demo:
        logger.warning(
            "DEMO_MODE_FORCE is enabled. This should ONLY be used for automated testing."
        )
        return True

    if is_production_environment():
        if _demo_mode_requested:
            logger.error(
                "DEMO_MODE requested in PRODUCTION environment. "
                "This is BLOCKED for security reasons. "
                "Set ENVIRONMENT=development to enable demo mode."
            )
        return False

    return _demo_mode_requested


def get_demo_mode_status() -> dict[str, Any]:
    """Get comprehensive demo mode status information."""
    allowed = is_demo_mode_allowed()
    return {
        "demo_mode_enabled": allowed,
        "environment": _current_env,
        "is_production": is_production_environment(),
        "demo_mode_requested": _demo_mode_requested,
        "demo_mode_allowed": allowed,
        "security_warning": (
            "Demo mode allows unauthenticated access. NEVER enable in production!"
            if allowed and is_production_environment()
            else None
        ),
    }


def require_demo_mode_allowed(func: Callable) -> Callable:
    """
    Decorator to ensure demo mode is allowed before executing.

    Use on functions that should only run in demo mode.
    """

    @wraps(func)
    async def async_wrapper(*args, **kwargs):
        if not is_demo_mode_allowed():
            raise RuntimeError(
                f"Function {func.__name__} requires demo mode, "
                "but demo mode is not allowed in this environment."
            )
        return await func(*args, **kwargs)

    @wraps(func)
    def sync_wrapper(*args, **kwargs):
        if not is_demo_mode_allowed():
            raise RuntimeError(
                f"Function {func.__name__} requires demo mode, "
                "but demo mode is not allowed in this environment."
            )
        return func(*args, **kwargs)

    import asyncio

    if asyncio.iscoroutinefunction(func):
        return async_wrapper
    return sync_wrapper


def log_demo_mode_access(user_id: str, action: str, details: dict[str, Any] | None = None):
    """Log demo mode access for audit trail."""
    logger.warning(
        "demo_mode_access",
        extra={
            "user_id": user_id,
            "action": action,
            "details": details or {},
            "environment": _current_env,
            "security_note": "Unauthenticated demo access",
        },
    )


DEMO_MODE = is_demo_mode_allowed()

if DEMO_MODE:
    logger.warning(
        "SECURITY WARNING: Demo mode is ENABLED. "
        f"Environment: {_current_env}. "
        "Unauthenticated access is allowed. "
        "This should NEVER be enabled in production!"
    )
