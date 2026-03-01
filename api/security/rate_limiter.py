"""
Rate limiting configuration for the API.

Uses slowapi to prevent brute-force attacks on authentication endpoints.
"""

import os
from collections.abc import Callable

from slowapi import Limiter
from slowapi.util import get_remote_address
from starlette.requests import Request

# Check if we're in test mode
TESTING = os.environ.get("TESTING", "0") == "1"


def get_client_identifier(request: Request) -> str:
    """
    Get unique identifier for rate limiting.

    Uses X-Forwarded-For header if behind proxy, otherwise remote address.
    For authenticated requests, includes user ID for per-user limits.
    """
    # In test mode, use a unique identifier per test to avoid rate limit collisions
    if TESTING:
        return "test-client"

    # Try to get forwarded IP (for reverse proxy setups)
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        # Take the first IP in the chain (original client)
        client_ip = forwarded.split(",")[0].strip()
    else:
        client_ip = get_remote_address(request)

    # Include user ID if authenticated (for per-user rate limits)
    if hasattr(request.state, "user_id"):
        return f"{client_ip}:{request.state.user_id}"

    return client_ip


# Create limiter instance with test mode consideration
limiter = Limiter(
    key_func=get_client_identifier,
    default_limits=["1000/minute"] if TESTING else ["100/minute"],
    storage_uri="memory://",  # Use Redis URI in production: "redis://localhost:6379"
    enabled=not TESTING,  # Disable rate limiting in test mode
)


# Rate limit configurations for different endpoint types
class RateLimits:
    """Rate limit configurations."""

    # Auth endpoints - strict limits to prevent brute force
    LOGIN = "5/minute"  # 5 login attempts per minute
    REGISTER = "3/minute"  # 3 registration attempts per minute
    PASSWORD_RESET = "2/minute"  # 2 password reset requests per minute

    # Token operations
    REFRESH_TOKEN = "10/minute"  # 10 token refreshes per minute
    LOGOUT = "10/minute"  # 10 logout requests per minute

    # Key generation (computationally expensive)
    KEY_GENERATION = "5/minute"  # 5 key generations per minute

    # Job submission (resource intensive)
    JOB_SUBMIT = "10/minute"  # 10 job submissions per minute
    JOB_LIST = "60/minute"  # 60 list requests per minute

    # General API limits
    READ_OPERATIONS = "100/minute"  # 100 read operations per minute
    WRITE_OPERATIONS = "30/minute"  # 30 write operations per minute


def create_rate_limit_decorator(limit: str) -> Callable:
    """Create a rate limit decorator with the specified limit."""
    return limiter.limit(limit)
