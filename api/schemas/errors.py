"""
Standardized error responses for the API.

Provides consistent error format across all endpoints.
"""

from typing import Any

from pydantic import BaseModel, Field


class ErrorCode:
    """Standard error codes."""

    # Authentication errors (1xxx)
    UNAUTHORIZED = "UNAUTHORIZED"
    INVALID_TOKEN = "INVALID_TOKEN"
    TOKEN_EXPIRED = "TOKEN_EXPIRED"
    INVALID_CREDENTIALS = "INVALID_CREDENTIALS"
    ACCOUNT_DISABLED = "ACCOUNT_DISABLED"

    # Authorization errors (2xxx)
    FORBIDDEN = "FORBIDDEN"
    INSUFFICIENT_PERMISSIONS = "INSUFFICIENT_PERMISSIONS"
    RESOURCE_NOT_OWNED = "RESOURCE_NOT_OWNED"

    # Validation errors (3xxx)
    VALIDATION_ERROR = "VALIDATION_ERROR"
    INVALID_INPUT = "INVALID_INPUT"
    MISSING_FIELD = "MISSING_FIELD"
    INVALID_FORMAT = "INVALID_FORMAT"

    # Resource errors (4xxx)
    NOT_FOUND = "NOT_FOUND"
    ALREADY_EXISTS = "ALREADY_EXISTS"
    CONFLICT = "CONFLICT"

    # Server errors (5xxx)
    INTERNAL_ERROR = "INTERNAL_ERROR"
    SERVICE_UNAVAILABLE = "SERVICE_UNAVAILABLE"
    DATABASE_ERROR = "DATABASE_ERROR"
    EXTERNAL_SERVICE_ERROR = "EXTERNAL_SERVICE_ERROR"

    # Rate limiting (6xxx)
    RATE_LIMITED = "RATE_LIMITED"


class ErrorResponse(BaseModel):
    """Standard error response format."""

    error: str = Field(..., description="Error code")
    message: str = Field(..., description="Human-readable message")
    details: dict[str, Any] | None = Field(default=None, description="Additional details")
    request_id: str | None = Field(default=None, description="Request tracking ID")

    class Config:
        json_schema_extra = {
            "example": {
                "error": "VALIDATION_ERROR",
                "message": "Invalid input provided",
                "details": {"field": "username", "reason": "Must be 3-50 characters"},
                "request_id": "req-abc123",
            }
        }


class ValidationErrorDetail(BaseModel):
    """Details for a single validation error."""

    field: str
    message: str
    value: Any | None = None
    constraint: str | None = None


class ValidationErrorResponse(ErrorResponse):
    """Validation error response with field details."""

    error: str = ErrorCode.VALIDATION_ERROR
    details: dict[str, list[ValidationErrorDetail]] | None = None
