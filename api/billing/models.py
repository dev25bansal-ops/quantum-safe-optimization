"""
Billing and Usage Tracking Module.

Tracks API calls, quantum shots, compute time, and generates invoices.
"""

import logging
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class BillingPeriod(str, Enum):
    """Billing period options."""

    HOURLY = "hourly"
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"


class PaymentStatus(str, Enum):
    """Payment status."""

    PENDING = "pending"
    PAID = "paid"
    FAILED = "failed"
    REFUNDED = "refunded"


class InvoiceStatus(str, Enum):
    """Invoice status."""

    DRAFT = "draft"
    OPEN = "open"
    PAID = "paid"
    VOID = "void"
    UNCOLLECTIBLE = "uncollectible"


class ResourceType(str, Enum):
    """Billable resource types."""

    API_CALL = "api_call"
    JOB_SUBMISSION = "job_submission"
    QUANTUM_SHOT = "quantum_shot"
    COMPUTE_TIME = "compute_time"  # seconds
    STORAGE = "storage"  # MB-hours
    KEY_GENERATION = "key_generation"
    WEBHOOK_CALL = "webhook_call"


# Pricing per unit (in USD)
PRICING: dict[ResourceType, float] = {
    ResourceType.API_CALL: 0.0001,  # $0.0001 per call
    ResourceType.JOB_SUBMISSION: 0.01,  # $0.01 per job
    ResourceType.QUANTUM_SHOT: 0.00001,  # $0.00001 per shot
    ResourceType.COMPUTE_TIME: 0.0001,  # $0.0001 per second
    ResourceType.STORAGE: 0.00001,  # $0.00001 per MB-hour
    ResourceType.KEY_GENERATION: 0.05,  # $0.05 per key
    ResourceType.WEBHOOK_CALL: 0.0005,  # $0.0005 per webhook
}


@dataclass
class UsageEvent:
    """A single usage event for billing."""

    event_id: str
    tenant_id: str
    user_id: str
    resource_type: ResourceType
    quantity: int
    unit_price: float
    total_price: float
    timestamp: datetime
    metadata: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def create(
        cls,
        tenant_id: str,
        user_id: str,
        resource_type: ResourceType,
        quantity: int = 1,
        metadata: dict[str, Any] | None = None,
    ) -> "UsageEvent":
        """Create a usage event."""
        unit_price = PRICING.get(resource_type, 0.0)
        total_price = unit_price * quantity

        return cls(
            event_id=f"evt_{uuid4().hex[:16]}",
            tenant_id=tenant_id,
            user_id=user_id,
            resource_type=resource_type,
            quantity=quantity,
            unit_price=unit_price,
            total_price=total_price,
            timestamp=datetime.now(UTC),
            metadata=metadata or {},
        )


@dataclass
class InvoiceLineItem:
    """A line item on an invoice."""

    resource_type: ResourceType
    quantity: int
    unit_price: float
    total_price: float
    period_start: datetime
    period_end: datetime


@dataclass
class Invoice:
    """Billing invoice for a tenant."""

    invoice_id: str
    tenant_id: str
    period_start: datetime
    period_end: datetime
    line_items: list[InvoiceLineItem]
    subtotal: float
    tax: float
    total: float
    status: InvoiceStatus = InvoiceStatus.OPEN
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    paid_at: datetime | None = None
    payment_id: str | None = None

    @classmethod
    def create(
        cls,
        tenant_id: str,
        period_start: datetime,
        period_end: datetime,
        events: list[UsageEvent],
    ) -> "Invoice":
        """Create an invoice from usage events."""
        # Aggregate events by resource type
        aggregated: dict[ResourceType, list[UsageEvent]] = {}
        for event in events:
            if event.resource_type not in aggregated:
                aggregated[event.resource_type] = []
            aggregated[event.resource_type].append(event)

        # Create line items
        line_items: list[InvoiceLineItem] = []
        subtotal = 0.0

        for resource_type, resource_events in aggregated.items():
            quantity = sum(e.quantity for e in resource_events)
            unit_price = PRICING.get(resource_type, 0.0)
            total_price = unit_price * quantity

            line_items.append(
                InvoiceLineItem(
                    resource_type=resource_type,
                    quantity=quantity,
                    unit_price=unit_price,
                    total_price=total_price,
                    period_start=period_start,
                    period_end=period_end,
                )
            )
            subtotal += total_price

        # Calculate tax (10% for example)
        tax = subtotal * 0.10
        total = subtotal + tax

        return cls(
            invoice_id=f"inv_{uuid4().hex[:12]}",
            tenant_id=tenant_id,
            period_start=period_start,
            period_end=period_end,
            line_items=line_items,
            subtotal=subtotal,
            tax=tax,
            total=total,
        )


# Pydantic models for API


class UsageEventCreate(BaseModel):
    """Request to record a usage event."""

    resource_type: ResourceType
    quantity: int = Field(default=1, ge=1)
    metadata: dict[str, Any] | None = None


class UsageEventResponse(BaseModel):
    """Usage event response."""

    event_id: str
    tenant_id: str
    user_id: str
    resource_type: ResourceType
    quantity: int
    unit_price: float
    total_price: float
    timestamp: str


class UsageSummary(BaseModel):
    """Usage summary for a period."""

    tenant_id: str
    period_start: str
    period_end: str
    total_events: int
    total_cost: float
    by_resource: dict[str, dict[str, Any]]


class InvoiceResponse(BaseModel):
    """Invoice response."""

    invoice_id: str
    tenant_id: str
    period_start: str
    period_end: str
    status: InvoiceStatus
    subtotal: float
    tax: float
    total: float
    line_items: list[dict[str, Any]]
    created_at: str
    paid_at: str | None
    payment_url: str | None


class PricingResponse(BaseModel):
    """Pricing information."""

    resource_type: str
    unit: str
    price_usd: float


class CostEstimateRequest(BaseModel):
    """Request for cost estimate."""

    shots: int = Field(default=1024)
    jobs: int = Field(default=1)
    compute_seconds: float = Field(default=60)
    storage_mb_hours: float = Field(default=100)


class CostEstimateResponse(BaseModel):
    """Cost estimate response."""

    shots_cost: float
    jobs_cost: float
    compute_cost: float
    storage_cost: float
    total_cost: float
    currency: str = "USD"


# In-memory storage
_usage_events: dict[str, list[UsageEvent]] = {}
_invoices: dict[str, list[Invoice]] = {}


def record_usage(
    tenant_id: str,
    user_id: str,
    resource_type: ResourceType,
    quantity: int = 1,
    metadata: dict[str, Any] | None = None,
) -> UsageEvent:
    """Record a usage event."""
    event = UsageEvent.create(
        tenant_id=tenant_id,
        user_id=user_id,
        resource_type=resource_type,
        quantity=quantity,
        metadata=metadata,
    )

    if tenant_id not in _usage_events:
        _usage_events[tenant_id] = []
    _usage_events[tenant_id].append(event)

    logger.debug(f"Recorded usage: {event.event_id} - {resource_type.value} x{quantity}")

    return event


def get_usage_summary(
    tenant_id: str,
    period_start: datetime,
    period_end: datetime,
) -> UsageSummary:
    """Get usage summary for a period."""
    events = [
        e for e in _usage_events.get(tenant_id, []) if period_start <= e.timestamp <= period_end
    ]

    by_resource: dict[str, dict[str, Any]] = {}
    total_cost = 0.0

    for event in events:
        rt = event.resource_type.value
        if rt not in by_resource:
            by_resource[rt] = {"quantity": 0, "cost": 0.0, "events": 0}
        by_resource[rt]["quantity"] += event.quantity
        by_resource[rt]["cost"] += event.total_price
        by_resource[rt]["events"] += 1
        total_cost += event.total_price

    return UsageSummary(
        tenant_id=tenant_id,
        period_start=period_start.isoformat(),
        period_end=period_end.isoformat(),
        total_events=len(events),
        total_cost=total_cost,
        by_resource=by_resource,
    )


def generate_invoice(
    tenant_id: str,
    period_start: datetime,
    period_end: datetime,
) -> Invoice:
    """Generate an invoice for a billing period."""
    events = [
        e for e in _usage_events.get(tenant_id, []) if period_start <= e.timestamp <= period_end
    ]

    invoice = Invoice.create(
        tenant_id=tenant_id,
        period_start=period_start,
        period_end=period_end,
        events=events,
    )

    if tenant_id not in _invoices:
        _invoices[tenant_id] = []
    _invoices[tenant_id].append(invoice)

    logger.info(f"Generated invoice: {invoice.invoice_id} - ${invoice.total:.2f}")

    return invoice


def estimate_cost(
    shots: int = 1024,
    jobs: int = 1,
    compute_seconds: float = 60,
    storage_mb_hours: float = 100,
) -> CostEstimateResponse:
    """Estimate cost for given resources."""
    shots_cost = shots * PRICING[ResourceType.QUANTUM_SHOT]
    jobs_cost = jobs * PRICING[ResourceType.JOB_SUBMISSION]
    compute_cost = compute_seconds * PRICING[ResourceType.COMPUTE_TIME]
    storage_cost = storage_mb_hours * PRICING[ResourceType.STORAGE]

    total_cost = shots_cost + jobs_cost + compute_cost + storage_cost

    return CostEstimateResponse(
        shots_cost=shots_cost,
        jobs_cost=jobs_cost,
        compute_cost=compute_cost,
        storage_cost=storage_cost,
        total_cost=total_cost,
    )
