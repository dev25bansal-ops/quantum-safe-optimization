"""
Comprehensive error handling module.

Provides standardized error handling, custom exceptions, and error response
formatting for consistent error reporting across the application.
"""

import logging
import traceback
from typing import Any, Dict, Optional, List
from datetime import datetime
from enum import Enum
from fastapi import HTTPException, Request, status
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class ErrorCode(str, Enum):
    """Standard error codes for the application."""
    
    # General errors
    INTERNAL_ERROR = "INTERNAL_ERROR"
    INVALID_REQUEST = "INVALID_REQUEST"
    NOT_FOUND = "NOT_FOUND"
    CONFLICT = "CONFLICT"
    RATE_LIMIT_EXCEEDED = "RATE_LIMIT_EXCEEDED"
    
    # Authentication errors
    UNAUTHORIZED = "UNAUTHORIZED"
    INVALID_TOKEN = "INVALID_TOKEN"
    TOKEN_EXPIRED = "TOKEN_EXPIRED"
    TOKEN_REVOKED = "TOKEN_REVOKED"
    INVALID_CREDENTIALS = "INVALID_CREDENTIALS"
    
    # Authorization errors
    FORBIDDEN = "FORBIDDEN"
    INSUFFICIENT_PERMISSIONS = "INSUFFICIENT_PERMISSIONS"
    
    # Validation errors
    VALIDATION_ERROR = "VALIDATION_ERROR"
    INVALID_INPUT = "INVALID_INPUT"
    MISSING_REQUIRED_FIELD = "MISSING_REQUIRED_FIELD"
    INVALID_FORMAT = "INVALID_FORMAT"
    OUT_OF_RANGE = "OUT_OF_RANGE"
    
    # Quantum job errors
    JOB_NOT_FOUND = "JOB_NOT_FOUND"
    JOB_ALREADY_EXISTS = "JOB_ALREADY_EXISTS"
    JOB_FAILED = "JOB_FAILED"
    JOB_TIMEOUT = "JOB_TIMEOUT"
    INVALID_PROBLEM_TYPE = "INVALID_PROBLEM_TYPE"
    INVALID_BACKEND = "INVALID_BACKEND"
    QUANTUM_ERROR = "QUANTUM_ERROR"
    
    # Resource errors
    RESOURCE_EXHAUSTED = "RESOURCE_EXHAUSTED"
    QUOTA_EXCEEDED = "QUOTA_EXCEEDED"
    
    # Security errors
    SECURITY_VIOLATION = "SECURITY_VIOLATION"
    MALICIOUS_INPUT = "MALICIOUS_INPUT"
    SUSPICIOUS_ACTIVITY = "SUSPICIOUS_ACTIVITY"
    
    # External service errors
    EXTERNAL_SERVICE_ERROR = "EXTERNAL_SERVICE_ERROR"
    EXTERNAL_SERVICE_UNAVAILABLE = "EXTERNAL_SERVICE_UNAVAILABLE"
    EXTERNAL_SERVICE_TIMEOUT = "EXTERNAL_SERVICE_TIMEOUT"
    
    # Database errors
    DATABASE_ERROR = "DATABASE_ERROR"
    DATABASE_CONNECTION_ERROR = "DATABASE_CONNECTION_ERROR"
    DATABASE_QUERY_ERROR = "DATABASE_QUERY_ERROR"
    
    # Crypto errors
    CRYPTO_ERROR = "CRYPTO_ERROR"
    ENCRYPTION_FAILED = "ENCRYPTION_FAILED"
    DECRYPTION_FAILED = "DECRYPTION_FAILED"
    SIGNATURE_VERIFICATION_FAILED = "SIGNATURE_VERIFICATION_FAILED"


class ErrorSeverity(str, Enum):
    """Error severity levels."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class AppError(Exception):
    """Base application error."""
    
    def __init__(
        self,
        message: str,
        code: ErrorCode = ErrorCode.INTERNAL_ERROR,
        status_code: int = status.HTTP_500_INTERNAL_SERVER_ERROR,
        details: Optional[Dict[str, Any]] = None,
        severity: ErrorSeverity = ErrorSeverity.MEDIUM,
        internal_message: Optional[str] = None,
        cause: Optional[Exception] = None
    ):
        self.message = message
        self.code = code
        self.status_code = status_code
        self.details = details or {}
        self.severity = severity
        self.internal_message = internal_message or message
        self.cause = cause
        self.timestamp = datetime.now()
        
        # Log the error
        self._log_error()
        
        super().__init__(self.message)
    
    def _log_error(self):
        """Log the error with appropriate level."""
        log_data = {
            "error_code": self.code,
            "severity": self.severity,
            "message": self.internal_message,
            "details": self.details,
        }
        
        if self.cause:
            log_data["cause"] = str(self.cause)
            log_data["traceback"] = traceback.format_exception(type(self.cause), self.cause, self.cause.__traceback__)
        
        if self.severity == ErrorSeverity.CRITICAL:
            logger.critical(f"CRITICAL ERROR: {self.code}", extra=log_data)
        elif self.severity == ErrorSeverity.HIGH:
            logger.error(f"HIGH ERROR: {self.code}", extra=log_data)
        elif self.severity == ErrorSeverity.MEDIUM:
            logger.warning(f"MEDIUM ERROR: {self.code}", extra=log_data)
        else:
            logger.info(f"LOW ERROR: {self.code}", extra=log_data)
    
    def to_dict(self, include_internal: bool = False) -> Dict[str, Any]:
        """Convert error to dictionary."""
        error_dict = {
            "error": self.code,
            "message": self.message,
            "timestamp": self.timestamp.isoformat(),
        }
        
        if self.details:
            error_dict["details"] = self.details
        
        if include_internal:
            error_dict["internal_message"] = self.internal_message
            if self.cause:
                error_dict["cause"] = str(self.cause)
        
        return error_dict
    
    def to_http_exception(self) -> HTTPException:
        """Convert to FastAPI HTTPException."""
        return HTTPException(
            status_code=self.status_code,
            detail=self.to_dict()
        )


class ValidationError(AppError):
    """Validation error."""
    
    def __init__(
        self,
        message: str,
        field: Optional[str] = None,
        value: Any = None,
        details: Optional[Dict[str, Any]] = None
    ):
        error_details = details or {}
        if field:
            error_details["field"] = field
        if value is not None:
            error_details["value"] = str(value)[:100]  # Limit value length
        
        super().__init__(
            message=message,
            code=ErrorCode.VALIDATION_ERROR,
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            details=error_details,
            severity=ErrorSeverity.LOW
        )


class AuthenticationError(AppError):
    """Authentication error."""
    
    def __init__(
        self,
        message: str = "Authentication required",
        code: ErrorCode = ErrorCode.UNAUTHORIZED,
        details: Optional[Dict[str, Any]] = None
    ):
        super().__init__(
            message=message,
            code=code,
            status_code=status.HTTP_401_UNAUTHORIZED,
            details=details,
            severity=ErrorSeverity.HIGH
        )


class AuthorizationError(AppError):
    """Authorization error."""
    
    def __init__(
        self,
        message: str = "Insufficient permissions",
        details: Optional[Dict[str, Any]] = None
    ):
        super().__init__(
            message=message,
            code=ErrorCode.FORBIDDEN,
            status_code=status.HTTP_403_FORBIDDEN,
            details=details,
            severity=ErrorSeverity.HIGH
        )


class NotFoundError(AppError):
    """Resource not found error."""
    
    def __init__(
        self,
        resource_type: str = "Resource",
        resource_id: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None
    ):
        message = f"{resource_type} not found"
        if resource_id:
            message += f": {resource_id}"
        
        error_details = details or {}
        error_details["resource_type"] = resource_type
        if resource_id:
            error_details["resource_id"] = resource_id
        
        super().__init__(
            message=message,
            code=ErrorCode.NOT_FOUND,
            status_code=status.HTTP_404_NOT_FOUND,
            details=error_details,
            severity=ErrorSeverity.LOW
        )


class ConflictError(AppError):
    """Resource conflict error."""
    
    def __init__(
        self,
        message: str = "Resource conflict",
        details: Optional[Dict[str, Any]] = None
    ):
        super().__init__(
            message=message,
            code=ErrorCode.CONFLICT,
            status_code=status.HTTP_409_CONFLICT,
            details=details,
            severity=ErrorSeverity.MEDIUM
        )


class RateLimitError(AppError):
    """Rate limit exceeded error."""
    
    def __init__(
        self,
        message: str = "Rate limit exceeded",
        retry_after: Optional[int] = None,
        details: Optional[Dict[str, Any]] = None
    ):
        error_details = details or {}
        if retry_after:
            error_details["retry_after"] = retry_after
        
        super().__init__(
            message=message,
            code=ErrorCode.RATE_LIMIT_EXCEEDED,
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            details=error_details,
            severity=ErrorSeverity.MEDIUM
        )


class JobError(AppError):
    """Quantum job error."""
    
    def __init__(
        self,
        message: str,
        job_id: Optional[str] = None,
        code: ErrorCode = ErrorCode.JOB_FAILED,
        details: Optional[Dict[str, Any]] = None
    ):
        error_details = details or {}
        if job_id:
            error_details["job_id"] = job_id
        
        super().__init__(
            message=message,
            code=code,
            status_code=status.HTTP_400_BAD_REQUEST,
            details=error_details,
            severity=ErrorSeverity.MEDIUM
        )


class SecurityError(AppError):
    """Security violation error."""
    
    def __init__(
        self,
        message: str = "Security violation detected",
        code: ErrorCode = ErrorCode.SECURITY_VIOLATION,
        details: Optional[Dict[str, Any]] = None
    ):
        super().__init__(
            message=message,
            code=code,
            status_code=status.HTTP_403_FORBIDDEN,
            details=details,
            severity=ErrorSeverity.CRITICAL
        )


class ExternalServiceError(AppError):
    """External service error."""
    
    def __init__(
        self,
        service_name: str,
        message: str = "External service error",
        code: ErrorCode = ErrorCode.EXTERNAL_SERVICE_ERROR,
        details: Optional[Dict[str, Any]] = None
    ):
        error_details = details or {}
        error_details["service"] = service_name
        
        super().__init__(
            message=message,
            code=code,
            status_code=status.HTTP_502_BAD_GATEWAY,
            details=error_details,
            severity=ErrorSeverity.HIGH
        )


class DatabaseError(AppError):
    """Database error."""
    
    def __init__(
        self,
        message: str = "Database error",
        code: ErrorCode = ErrorCode.DATABASE_ERROR,
        details: Optional[Dict[str, Any]] = None,
        cause: Optional[Exception] = None
    ):
        super().__init__(
            message=message,
            code=code,
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            details=details,
            severity=ErrorSeverity.HIGH,
            cause=cause
        )


class CryptoError(AppError):
    """Cryptography error."""
    
    def __init__(
        self,
        message: str = "Cryptography error",
        code: ErrorCode = ErrorCode.CRYPTO_ERROR,
        details: Optional[Dict[str, Any]] = None,
        cause: Optional[Exception] = None
    ):
        super().__init__(
            message=message,
            code=code,
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            details=details,
            severity=ErrorSeverity.CRITICAL,
            cause=cause
        )


class ErrorResponse(BaseModel):
    """Standard error response model."""
    
    error: str = Field(..., description="Error code")
    message: str = Field(..., description="Human-readable error message")
    timestamp: str = Field(..., description="Error timestamp")
    request_id: Optional[str] = Field(None, description="Request ID for tracing")
    details: Optional[Dict[str, Any]] = Field(None, description="Additional error details")


class ValidationErrorDetail(BaseModel):
    """Validation error detail."""
    
    field: str = Field(..., description="Field that failed validation")
    message: str = Field(..., description="Validation error message")
    value: Optional[str] = Field(None, description="Invalid value")


class ValidationErrorResponse(ErrorResponse):
    """Validation error response with field details."""
    
    details: List[ValidationErrorDetail] = Field(..., description="Validation error details")


def handle_exception(
    exc: Exception,
    request: Optional[Request] = None,
    include_internal: bool = False
) -> ErrorResponse:
    """Handle an exception and return standardized error response."""
    
    # Get request ID if available
    request_id = None
    if request:
        request_id = request.headers.get("X-Request-ID") or getattr(request.state, "request_id", None)
    
    # Handle AppError subclasses
    if isinstance(exc, AppError):
        error_dict = exc.to_dict(include_internal=include_internal)
        error_dict["request_id"] = request_id
        return ErrorResponse(**error_dict)
    
    # Handle HTTPException
    if isinstance(exc, HTTPException):
        return ErrorResponse(
            error=ErrorCode.INTERNAL_ERROR.value,
            message=str(exc.detail),
            timestamp=datetime.now().isoformat(),
            request_id=request_id,
            details={"status_code": exc.status_code}
        )
    
    # Handle unknown exceptions
    logger.exception(
        "Unhandled exception",
        exc_info=exc,
        extra={
            "request_id": request_id,
            "path": request.url.path if request else None,
            "method": request.method if request else None,
        }
    )
    
    return ErrorResponse(
        error=ErrorCode.INTERNAL_ERROR.value,
        message="An internal error occurred",
        timestamp=datetime.now().isoformat(),
        request_id=request_id
    )


def create_error_response(
    error_code: ErrorCode,
    message: str,
    status_code: int = status.HTTP_500_INTERNAL_SERVER_ERROR,
    details: Optional[Dict[str, Any]] = None,
    request_id: Optional[str] = None
) -> ErrorResponse:
    """Create a standardized error response."""
    
    return ErrorResponse(
        error=error_code.value,
        message=message,
        timestamp=datetime.now().isoformat(),
        request_id=request_id,
        details=details
    )


def create_validation_error(
    field: str,
    message: str,
    value: Any = None,
    request_id: Optional[str] = None
) -> ValidationErrorResponse:
    """Create a validation error response."""
    
    return ValidationErrorResponse(
        error=ErrorCode.VALIDATION_ERROR.value,
        message="Validation failed",
        timestamp=datetime.now().isoformat(),
        request_id=request_id,
        details=[
            ValidationErrorDetail(
                field=field,
                message=message,
                value=str(value)[:100] if value is not None else None
            )
        ]
    )


async def async_error_handler(
    request: Request,
    exc: Exception
) -> ErrorResponse:
    """Async error handler for FastAPI."""
    
    response = handle_exception(exc, request)
    
    # Log security-related errors
    if isinstance(exc, (SecurityError, AuthenticationError, AuthorizationError)):
        logger.warning(
            f"Security error on {request.method} {request.url.path}",
            extra={
                "error_code": response.error,
                "request_id": response.request_id,
                "client_ip": request.client.host if request.client else None,
            }
        )
    
    return response


def wrap_errors(func):
    """Decorator to wrap functions with error handling."""
    
    async def async_wrapper(*args, **kwargs):
        try:
            return await func(*args, **kwargs)
        except AppError:
            raise
        except HTTPException:
            raise
        except Exception as e:
            logger.exception(f"Unexpected error in {func.__name__}")
            raise AppError(
                message="An unexpected error occurred",
                cause=e
            )
    
    def sync_wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except AppError:
            raise
        except HTTPException:
            raise
        except Exception as e:
            logger.exception(f"Unexpected error in {func.__name__}")
            raise AppError(
                message="An unexpected error occurred",
                cause=e
            )
    
    if asyncio.iscoroutinefunction(func):
        return async_wrapper
    else:
        return sync_wrapper


import asyncio