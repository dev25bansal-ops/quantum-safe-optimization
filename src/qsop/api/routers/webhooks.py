"""Webhook statistics endpoints."""

from __future__ import annotations

from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Query
from pydantic import BaseModel, ConfigDict

router = APIRouter()


class WebhookStatsSummary(BaseModel):
    """Summary of webhook statistics."""

    total_webhooks: int
    active_webhooks: int
    successful_deliveries_24h: int
    failed_deliveries_24h: int
    avg_delivery_time_ms: float
    success_rate_24h: float

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "total_webhooks": 15,
                "active_webhooks": 12,
                "successful_deliveries_24h": 1425,
                "failed_deliveries_24h": 12,
                "avg_delivery_time_ms": 245.5,
                "success_rate_24h": 0.9917,
            }
        }
    )


class WebhookAttemptSummary(BaseModel):
    """Summary of webhook attempt statistics."""

    webhook_id: str
    webhook_name: str | None
    total_attempts: int
    successful_attempts: int
    failed_attempts: int
    average_response_time_ms: float
    last_success_at: datetime | None
    last_failure_at: datetime | None
    status_code_distribution: dict[int, int]

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "webhook_id": "webhook-123",
                "webhook_name": "Job Completion Callback",
                "total_attempts": 1500,
                "successful_attempts": 1485,
                "failed_attempts": 15,
                "average_response_time_ms": 234.5,
                "last_success_at": "2024-01-15T10:28:00Z",
                "last_failure_at": "2024-01-15T09:45:00Z",
                "status_code_distribution": {
                    "200": 1485,
                    "500": 10,
                    "502": 5,
                },
            }
        }
    )


class WebhookErrorDetail(BaseModel):
    """Detailed error information for webhook failures."""

    error_id: str
    webhook_id: str
    error_type: str
    error_message: str
    status_code: int | None
    response_body: str | None
    timestamp: datetime
    retry_count: int
    will_retry: bool

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "error_id": "err-456",
                "webhook_id": "webhook-123",
                "error_type": "ConnectionError",
                "error_message": "Connection timeout after 30 seconds",
                "status_code": None,
                "response_body": None,
                "timestamp": "2024-01-15T09:45:00Z",
                "retry_count": 2,
                "will_retry": True,
            }
        }
    )


class WebhookDetailedStatsResponse(BaseModel):
    """Detailed webhook statistics response."""

    summary: WebhookStatsSummary
    webhook_stats: list[WebhookAttemptSummary]
    recent_errors: list[WebhookErrorDetail]
    time_range_hours: int

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "summary": {
                    "total_webhooks": 15,
                    "active_webhooks": 12,
                    "successful_deliveries_24h": 1425,
                    "failed_deliveries_24h": 12,
                    "avg_delivery_time_ms": 245.5,
                    "success_rate_24h": 0.9917,
                },
                "webhook_stats": [
                    {
                        "webhook_id": "webhook-123",
                        "webhook_name": "Job Completion Callback",
                        "total_attempts": 1500,
                        "successful_attempts": 1485,
                        "failed_attempts": 15,
                        "average_response_time_ms": 234.5,
                        "last_success_at": "2024-01-15T10:28:00Z",
                        "last_failure_at": "2024-01-15T09:45:00Z",
                        "status_code_distribution": {
                            "200": 1485,
                            "500": 10,
                            "502": 5,
                        },
                    }
                ],
                "recent_errors": [
                    {
                        "error_id": "err-456",
                        "webhook_id": "webhook-123",
                        "error_type": "ConnectionError",
                        "error_message": "Connection timeout after 30 seconds",
                        "status_code": None,
                        "response_body": None,
                        "timestamp": "2024-01-15T09:45:00Z",
                        "retry_count": 2,
                        "will_retry": True,
                    }
                ],
                "time_range_hours": 24,
            }
        }
    )


@router.get("", response_model=WebhookDetailedStatsResponse)
async def get_webhook_stats(
    hours: Annotated[int, Query(ge=1, le=168, description="Time range in hours")] = 24,
    webhook_id: Annotated[str | None, Query(description="Filter by specific webhook")] = None,
) -> WebhookDetailedStatsResponse:
    """
    Get webhook delivery statistics.

    Returns statistics about webhook deliveries, success rates, and recent errors.
    """
    # In production, this would query the webhook delivery logs
    # For now, return mock data

    summary = WebhookStatsSummary(
        total_webhooks=15,
        active_webhooks=12,
        successful_deliveries_24h=1425,
        failed_deliveries_24h=12,
        avg_delivery_time_ms=245.5,
        success_rate_24h=0.9917,
    )

    webhook_stats = [
        WebhookAttemptSummary(
            webhook_id="webhook-123",
            webhook_name="Job Completion Callback",
            total_attempts=1500,
            successful_attempts=1485,
            failed_attempts=15,
            average_response_time_ms=234.5,
            last_success_at=datetime.utcnow(),
            last_failure_at=datetime.utcnow(),
            status_code_distribution={
                200: 1485,
                500: 10,
                502: 5,
            },
        )
    ]

    recent_errors = [
        WebhookErrorDetail(
            error_id="err-456",
            webhook_id="webhook-123",
            error_type="ConnectionError",
            error_message="Connection timeout after 30 seconds",
            status_code=None,
            response_body=None,
            timestamp=datetime.utcnow(),
            retry_count=2,
            will_retry=True,
        )
    ]

    return WebhookDetailedStatsResponse(
        summary=summary,
        webhook_stats=webhook_stats,
        recent_errors=recent_errors,
        time_range_hours=hours,
    )


@router.get("/{webhook_id}", response_model=WebhookAttemptSummary)
async def get_webhook_stats_by_id(
    webhook_id: str,
    hours: Annotated[int, Query(ge=1, le=168, description="Time range in hours")] = 24,
) -> WebhookAttemptSummary:
    """
    Get statistics for a specific webhook.
    """
    # In production, this would query the webhook delivery logs
    # For now, return mock data
    return WebhookAttemptSummary(
        webhook_id=webhook_id,
        webhook_name="Job Completion Callback",
        total_attempts=1500,
        successful_attempts=1485,
        failed_attempts=15,
        average_response_time_ms=234.5,
        last_success_at=datetime.utcnow(),
        last_failure_at=datetime.utcnow(),
        status_code_distribution={
            200: 1485,
            500: 10,
            502: 5,
        },
    )


@router.get("/{webhook_id}/errors", response_model=list[WebhookErrorDetail])
async def get_webhook_errors(
    webhook_id: str,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
) -> list[WebhookErrorDetail]:
    """
    Get recent errors for a specific webhook.
    """
    # In production, this would query the webhook delivery logs
    # For now, return mock data
    return [
        WebhookErrorDetail(
            error_id="err-456",
            webhook_id=webhook_id,
            error_type="ConnectionError",
            error_message="Connection timeout after 30 seconds",
            status_code=None,
            response_body=None,
            timestamp=datetime.utcnow(),
            retry_count=2,
            will_retry=True,
        )
    ]
