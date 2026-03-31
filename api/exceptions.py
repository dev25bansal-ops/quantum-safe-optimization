"""
Custom exceptions for QSOP API.

Use these instead of broad Exception catches.
"""

from typing import Any


class QSOPError(Exception):
    """Base exception for all QSOP errors."""

    def __init__(self, message: str, details: dict[str, Any] | None = None):
        super().__init__(message)
        self.message = message
        self.details = details or {}


# Authentication errors
class AuthenticationError(QSOPError):
    """Authentication failed."""

    pass


class InvalidTokenError(AuthenticationError):
    """Token is invalid or malformed."""

    pass


class TokenExpiredError(AuthenticationError):
    """Token has expired."""

    pass


class InvalidCredentialsError(AuthenticationError):
    """Invalid username or password."""

    pass


# Authorization errors
class AuthorizationError(QSOPError):
    """User lacks required permissions."""

    pass


class ResourceNotOwnedError(AuthorizationError):
    """User does not own the requested resource."""

    pass


# Resource errors
class ResourceNotFoundError(QSOPError):
    """Requested resource not found."""

    pass


class ResourceExistsError(QSOPError):
    """Resource already exists."""

    pass


class ResourceConflictError(QSOPError):
    """Resource conflict (e.g., concurrent modification)."""

    pass


# Validation errors
class ValidationError(QSOPError):
    """Input validation failed."""

    pass


class InvalidInputError(ValidationError):
    """Invalid input provided."""

    pass


class MissingFieldError(ValidationError):
    """Required field is missing."""

    pass


# Crypto errors
class CryptoError(QSOPError):
    """Cryptography operation failed."""

    pass


class KeyGenerationError(CryptoError):
    """Key generation failed."""

    pass


class EncryptionError(CryptoError):
    """Encryption operation failed."""

    pass


class DecryptionError(CryptoError):
    """Decryption operation failed."""

    pass


class SignatureError(CryptoError):
    """Signature operation failed."""

    pass


class InvalidSignatureError(SignatureError):
    """Signature verification failed."""

    pass


# Job errors
class JobError(QSOPError):
    """Job-related error."""

    pass


class JobNotFoundError(JobError):
    """Job not found."""

    pass


class JobSubmissionError(JobError):
    """Job submission failed."""

    pass


class JobExecutionError(JobError):
    """Job execution failed."""

    pass


class JobCancellationError(JobError):
    """Job cancellation failed."""

    pass


# Backend errors
class BackendError(QSOPError):
    """Quantum backend error."""

    pass


class BackendUnavailableError(BackendError):
    """Quantum backend is unavailable."""

    pass


class BackendTimeoutError(BackendError):
    """Quantum backend operation timed out."""

    pass


class BackendQuotaExceededError(BackendError):
    """Backend quota exceeded."""

    pass


# Database errors
class DatabaseError(QSOPError):
    """Database operation failed."""

    pass


class ConnectionError(DatabaseError):
    """Database connection failed."""

    pass


class QueryError(DatabaseError):
    """Database query failed."""

    pass


# Rate limiting errors
class RateLimitError(QSOPError):
    """Rate limit exceeded."""

    pass


# Webhook errors
class WebhookError(QSOPError):
    """Webhook delivery failed."""

    pass


class WebhookValidationError(WebhookError):
    """Webhook URL validation failed."""

    pass
