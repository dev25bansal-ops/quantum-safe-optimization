"""
Domain-specific exceptions for the Quantum-Safe Optimization Platform.

All domain errors inherit from DomainError to allow for unified error handling.
"""

from typing import Any


class DomainError(Exception):
    """Base exception for all domain-level errors."""

    def __init__(self, message: str, details: dict[str, Any] | None = None) -> None:
        """
        Initialize domain error.

        Args:
            message: Human-readable error description.
            details: Optional dictionary with additional error context.
        """
        super().__init__(message)
        self.message = message
        self.details = details or {}

    def __str__(self) -> str:
        if self.details:
            return f"{self.message} | Details: {self.details}"
        return self.message


class ValidationError(DomainError):
    """Raised when input validation fails."""

    def __init__(
        self,
        message: str,
        field: str | None = None,
        value: Any = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        """
        Initialize validation error.

        Args:
            message: Description of the validation failure.
            field: Name of the field that failed validation.
            value: The invalid value (be careful with sensitive data).
            details: Additional validation context.
        """
        error_details = details or {}
        if field:
            error_details["field"] = field
        if value is not None:
            error_details["value"] = value
        super().__init__(message, error_details)
        self.field = field
        self.value = value


class OptimizationError(DomainError):
    """Raised when an optimization algorithm fails."""

    def __init__(
        self,
        message: str,
        algorithm: str | None = None,
        iteration: int | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        """
        Initialize optimization error.

        Args:
            message: Description of the optimization failure.
            algorithm: Name of the algorithm that failed.
            iteration: Iteration number when failure occurred.
            details: Additional optimization context.
        """
        error_details = details or {}
        if algorithm:
            error_details["algorithm"] = algorithm
        if iteration is not None:
            error_details["iteration"] = iteration
        super().__init__(message, error_details)
        self.algorithm = algorithm
        self.iteration = iteration


class QuantumBackendError(DomainError):
    """Raised when quantum backend operations fail."""

    def __init__(
        self,
        message: str,
        backend: str | None = None,
        job_id: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        """
        Initialize quantum backend error.

        Args:
            message: Description of the backend failure.
            backend: Name of the quantum backend.
            job_id: ID of the failed job if applicable.
            details: Additional backend context.
        """
        error_details = details or {}
        if backend:
            error_details["backend"] = backend
        if job_id:
            error_details["job_id"] = job_id
        super().__init__(message, error_details)
        self.backend = backend
        self.job_id = job_id


class CryptoError(DomainError):
    """Raised when cryptographic operations fail."""

    def __init__(
        self,
        message: str,
        operation: str | None = None,
        algorithm: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        """
        Initialize crypto error.

        Args:
            message: Description of the cryptographic failure.
            operation: The operation that failed (encrypt, decrypt, sign, verify).
            algorithm: The algorithm being used.
            details: Additional cryptographic context.
        """
        error_details = details or {}
        if operation:
            error_details["operation"] = operation
        if algorithm:
            error_details["algorithm"] = algorithm
        super().__init__(message, error_details)
        self.operation = operation
        self.algorithm = algorithm


class KeyStoreError(DomainError):
    """Raised when key store operations fail."""

    def __init__(
        self,
        message: str,
        key_id: str | None = None,
        operation: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        """
        Initialize key store error.

        Args:
            message: Description of the key store failure.
            key_id: ID of the key involved (if applicable).
            operation: The operation that failed.
            details: Additional key store context.
        """
        error_details = details or {}
        if key_id:
            error_details["key_id"] = key_id
        if operation:
            error_details["operation"] = operation
        super().__init__(message, error_details)
        self.key_id = key_id
        self.operation = operation


class ArtifactError(DomainError):
    """Raised when artifact operations fail."""

    def __init__(
        self,
        message: str,
        artifact_id: str | None = None,
        artifact_type: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        """
        Initialize artifact error.

        Args:
            message: Description of the artifact failure.
            artifact_id: ID of the artifact involved.
            artifact_type: Type of the artifact.
            details: Additional artifact context.
        """
        error_details = details or {}
        if artifact_id:
            error_details["artifact_id"] = artifact_id
        if artifact_type:
            error_details["artifact_type"] = artifact_type
        super().__init__(message, error_details)
        self.artifact_id = artifact_id
        self.artifact_type = artifact_type


class JobError(DomainError):
    """Raised when job operations fail."""

    def __init__(
        self,
        message: str,
        job_id: str | None = None,
        status: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        """
        Initialize job error.

        Args:
            message: Description of the job failure.
            job_id: ID of the job involved.
            status: Current status of the job.
            details: Additional job context.
        """
        error_details = details or {}
        if job_id:
            error_details["job_id"] = job_id
        if status:
            error_details["status"] = status
        super().__init__(message, error_details)
        self.job_id = job_id
        self.status = status
