"""
Webhook System.

Provides webhook management, delivery, and retry logic for event notifications.
"""

import hashlib
import hmac
import json
import logging
import secrets
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from typing import Any

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field, HttpUrl

logger = logging.getLogger(__name__)

router = APIRouter()


class WebhookEvent(str, Enum):
    """Available webhook events."""

    JOB_CREATED = "job.created"
    JOB_STARTED = "job.started"
    JOB_PROGRESS = "job.progress"
    JOB_COMPLETED = "job.completed"
    JOB_FAILED = "job.failed"
    JOB_CANCELLED = "job.cancelled"
    USER_REGISTERED = "user.registered"
    USER_DELETED = "user.deleted"
    API_KEY_CREATED = "api_key.created"
    API_KEY_REVOKED = "api_key.revoked"
    ALERT_TRIGGERED = "alert.triggered"
    BILLING_USAGE = "billing.usage"


class WebhookStatus(str, Enum):
    """Webhook endpoint status."""

    ACTIVE = "active"
    DISABLED = "disabled"
    FAILED = "failed"


@dataclass
class WebhookDelivery:
    """Webhook delivery attempt."""

    id: str
    webhook_id: str
    event: str
    payload: dict[str, Any]
    status_code: int | None
    response: str | None
    delivered_at: str
    attempt: int
    success: bool


class WebhookCreate(BaseModel):
    """Request to create a webhook."""

    url: HttpUrl
    events: list[WebhookEvent] = Field(..., min_length=1)
    secret: str | None = None
    description: str | None = None
    enabled: bool = True


class WebhookUpdate(BaseModel):
    """Request to update a webhook."""

    url: HttpUrl | None = None
    events: list[WebhookEvent] | None = None
    secret: str | None = None
    description: str | None = None
    enabled: bool | None = None


class WebhookResponse(BaseModel):
    """Webhook response."""

    id: str
    url: str
    events: list[str]
    description: str | None
    enabled: bool
    status: str
    created_at: str
    last_delivery: str | None
    delivery_count: int
    failure_count: int


class WebhookDeliveryResponse(BaseModel):
    """Webhook delivery response."""

    id: str
    webhook_id: str
    event: str
    status_code: int | None
    success: bool
    delivered_at: str
    attempt: int


class WebhookList(BaseModel):
    """List of webhooks."""

    webhooks: list[WebhookResponse]
    total: int


# In-memory storage (replace with database in production)
_webhooks: dict[str, dict[str, Any]] = {}
_deliveries: list[WebhookDelivery] = []


def _generate_webhook_id() -> str:
    return f"wh_{secrets.token_hex(8)}"


def _generate_signature(secret: str, payload: str) -> str:
    """Generate HMAC signature for webhook payload."""
    return hmac.new(secret.encode(), payload.encode(), hashlib.sha256).hexdigest()


def get_user_id() -> str:
    return "user_default"


@router.post("/", response_model=WebhookResponse, status_code=201)
async def create_webhook(
    request: WebhookCreate,
    user_id: str = Depends(get_user_id),
):
    """Create a new webhook endpoint."""
    webhook_id = _generate_webhook_id()
    secret = request.secret or secrets.token_hex(32)

    _webhooks[webhook_id] = {
        "id": webhook_id,
        "url": str(request.url),
        "events": [e.value for e in request.events],
        "secret": secret,
        "description": request.description,
        "enabled": request.enabled,
        "status": WebhookStatus.ACTIVE.value,
        "created_at": datetime.now(UTC).isoformat(),
        "user_id": user_id,
        "delivery_count": 0,
        "failure_count": 0,
        "last_delivery": None,
    }

    logger.info("webhook_created", webhook_id=webhook_id, url=str(request.url))

    wh = _webhooks[webhook_id]
    return WebhookResponse(
        id=wh["id"],
        url=wh["url"],
        events=wh["events"],
        description=wh["description"],
        enabled=wh["enabled"],
        status=wh["status"],
        created_at=wh["created_at"],
        last_delivery=wh["last_delivery"],
        delivery_count=wh["delivery_count"],
        failure_count=wh["failure_count"],
    )


@router.get("/", response_model=WebhookList)
async def list_webhooks(
    user_id: str = Depends(get_user_id),
    limit: int = Query(default=20, le=100),
    offset: int = Query(default=0, ge=0),
):
    """List all webhooks."""
    user_webhooks = [wh for wh in _webhooks.values() if wh.get("user_id") == user_id]

    webhooks = []
    for wh in user_webhooks[offset : offset + limit]:
        webhooks.append(
            WebhookResponse(
                id=wh["id"],
                url=wh["url"],
                events=wh["events"],
                description=wh["description"],
                enabled=wh["enabled"],
                status=wh["status"],
                created_at=wh["created_at"],
                last_delivery=wh["last_delivery"],
                delivery_count=wh["delivery_count"],
                failure_count=wh["failure_count"],
            )
        )

    return WebhookList(webhooks=webhooks, total=len(user_webhooks))


@router.get("/{webhook_id}", response_model=WebhookResponse)
async def get_webhook(
    webhook_id: str,
    user_id: str = Depends(get_user_id),
):
    """Get a webhook by ID."""
    wh = _webhooks.get(webhook_id)
    if not wh:
        raise HTTPException(status_code=404, detail="Webhook not found")

    return WebhookResponse(
        id=wh["id"],
        url=wh["url"],
        events=wh["events"],
        description=wh["description"],
        enabled=wh["enabled"],
        status=wh["status"],
        created_at=wh["created_at"],
        last_delivery=wh["last_delivery"],
        delivery_count=wh["delivery_count"],
        failure_count=wh["failure_count"],
    )


@router.patch("/{webhook_id}", response_model=WebhookResponse)
async def update_webhook(
    webhook_id: str,
    request: WebhookUpdate,
    user_id: str = Depends(get_user_id),
):
    """Update a webhook."""
    wh = _webhooks.get(webhook_id)
    if not wh:
        raise HTTPException(status_code=404, detail="Webhook not found")

    if request.url is not None:
        wh["url"] = str(request.url)
    if request.events is not None:
        wh["events"] = [e.value for e in request.events]
    if request.secret is not None:
        wh["secret"] = request.secret
    if request.description is not None:
        wh["description"] = request.description
    if request.enabled is not None:
        wh["enabled"] = request.enabled

    return WebhookResponse(
        id=wh["id"],
        url=wh["url"],
        events=wh["events"],
        description=wh["description"],
        enabled=wh["enabled"],
        status=wh["status"],
        created_at=wh["created_at"],
        last_delivery=wh["last_delivery"],
        delivery_count=wh["delivery_count"],
        failure_count=wh["failure_count"],
    )


@router.delete("/{webhook_id}")
async def delete_webhook(
    webhook_id: str,
    user_id: str = Depends(get_user_id),
):
    """Delete a webhook."""
    if webhook_id not in _webhooks:
        raise HTTPException(status_code=404, detail="Webhook not found")

    del _webhooks[webhook_id]
    return {"status": "deleted", "webhook_id": webhook_id}


@router.get("/{webhook_id}/deliveries")
async def get_webhook_deliveries(
    webhook_id: str,
    user_id: str = Depends(get_user_id),
    limit: int = Query(default=50, le=200),
):
    """Get delivery history for a webhook."""
    if webhook_id not in _webhooks:
        raise HTTPException(status_code=404, detail="Webhook not found")

    deliveries = [
        WebhookDeliveryResponse(
            id=d.id,
            webhook_id=d.webhook_id,
            event=d.event,
            status_code=d.status_code,
            success=d.success,
            delivered_at=d.delivered_at,
            attempt=d.attempt,
        )
        for d in _deliveries
        if d.webhook_id == webhook_id
    ]

    return {"deliveries": deliveries[:limit], "total": len(deliveries)}


@router.post("/{webhook_id}/test")
async def test_webhook(
    webhook_id: str,
    user_id: str = Depends(get_user_id),
):
    """Test a webhook by sending a test event."""
    wh = _webhooks.get(webhook_id)
    if not wh:
        raise HTTPException(status_code=404, detail="Webhook not found")

    test_payload = {
        "event": "webhook.test",
        "webhook_id": webhook_id,
        "timestamp": datetime.now(UTC).isoformat(),
        "data": {"message": "This is a test webhook delivery"},
    }

    result = await deliver_webhook(webhook_id, "webhook.test", test_payload)

    return {
        "status": "success" if result.success else "failed",
        "status_code": result.status_code,
        "delivered_at": result.delivered_at,
    }


async def deliver_webhook(
    webhook_id: str,
    event: str,
    payload: dict[str, Any],
) -> WebhookDelivery:
    """Deliver a webhook to the endpoint."""
    wh = _webhooks.get(webhook_id)
    if not wh or not wh["enabled"]:
        return WebhookDelivery(
            id=f"del_{secrets.token_hex(8)}",
            webhook_id=webhook_id,
            event=event,
            payload=payload,
            status_code=None,
            response=None,
            delivered_at=datetime.now(UTC).isoformat(),
            attempt=1,
            success=False,
        )

    payload_str = json.dumps(payload, separators=(",", ":"))
    signature = _generate_signature(wh["secret"], payload_str)

    headers = {
        "Content-Type": "application/json",
        "X-Webhook-Event": event,
        "X-Webhook-ID": webhook_id,
        "X-Webhook-Signature": f"sha256={signature}",
        "X-Webhook-Timestamp": datetime.now(UTC).isoformat(),
    }

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                wh["url"],
                content=payload_str,
                headers=headers,
            )

        success = 200 <= response.status_code < 300

        wh["delivery_count"] += 1
        if not success:
            wh["failure_count"] += 1
        wh["last_delivery"] = datetime.now(UTC).isoformat()

        if success:
            wh["status"] = WebhookStatus.ACTIVE.value
        elif wh["failure_count"] >= 10:
            wh["status"] = WebhookStatus.FAILED.value
            logger.warning("webhook_marked_failed", webhook_id=webhook_id)

        delivery = WebhookDelivery(
            id=f"del_{secrets.token_hex(8)}",
            webhook_id=webhook_id,
            event=event,
            payload=payload,
            status_code=response.status_code,
            response=response.text[:500] if response.text else None,
            delivered_at=datetime.now(UTC).isoformat(),
            attempt=1,
            success=success,
        )

        _deliveries.append(delivery)
        logger.info(
            "webhook_delivered",
            webhook_id=webhook_id,
            event=event,
            success=success,
            status_code=response.status_code,
        )

        return delivery

    except Exception as e:
        wh["failure_count"] += 1
        wh["delivery_count"] += 1
        wh["last_delivery"] = datetime.now(UTC).isoformat()

        delivery = WebhookDelivery(
            id=f"del_{secrets.token_hex(8)}",
            webhook_id=webhook_id,
            event=event,
            payload=payload,
            status_code=None,
            response=str(e),
            delivered_at=datetime.now(UTC).isoformat(),
            attempt=1,
            success=False,
        )

        _deliveries.append(delivery)
        logger.error("webhook_delivery_failed", webhook_id=webhook_id, error=str(e))

        return delivery


async def trigger_webhook_event(event: str, data: dict[str, Any]) -> None:
    """Trigger webhooks for an event."""
    for webhook_id, wh in _webhooks.items():
        if not wh["enabled"]:
            continue
        if event not in wh["events"]:
            continue

        payload = {
            "event": event,
            "webhook_id": webhook_id,
            "timestamp": datetime.now(UTC).isoformat(),
            "data": data,
        }

        # Fire and forget (use task queue in production)
        await deliver_webhook(webhook_id, event, payload)
