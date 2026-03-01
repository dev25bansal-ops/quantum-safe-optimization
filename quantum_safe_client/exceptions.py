"""
QuantumSafe Client - Custom exceptions.
"""


class QuantumSafeError(Exception):
    """Base exception for QuantumSafe client errors."""

    def __init__(self, message: str = "An error occurred"):
        self.message = message
        super().__init__(self.message)


class AuthenticationError(QuantumSafeError):
    """Raised when authentication fails."""

    def __init__(self, message: str = "Authentication failed"):
        super().__init__(message)


class JobNotFoundError(QuantumSafeError):
    """Raised when a job is not found."""

    def __init__(self, message: str = "Job not found"):
        super().__init__(message)


class ValidationError(QuantumSafeError):
    """Raised when request validation fails."""

    def __init__(self, message: str = "Validation error"):
        super().__init__(message)


class RateLimitError(QuantumSafeError):
    """Raised when rate limit is exceeded."""

    def __init__(self, message: str = "Rate limit exceeded"):
        super().__init__(message)


class APIError(QuantumSafeError):
    """Raised for general API errors."""

    def __init__(self, message: str = "API error"):
        super().__init__(message)


class TimeoutError(QuantumSafeError):
    """Raised when an operation times out."""

    def __init__(self, message: str = "Operation timed out"):
        super().__init__(message)


class BackendError(QuantumSafeError):
    """Raised when a quantum backend error occurs."""

    def __init__(self, message: str = "Backend error"):
        super().__init__(message)


class CancellationError(QuantumSafeError):
    """Raised when job cancellation fails."""

    def __init__(self, message: str = "Failed to cancel job"):
        super().__init__(message)
