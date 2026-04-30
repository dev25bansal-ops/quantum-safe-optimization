"""
Billing API Endpoints.

Provides usage tracking, cost estimation, and invoice generation.
"""

import logging
from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends, Query

from .models import (
    CostEstimateRequest,
    CostEstimateResponse,
    InvoiceResponse,
    PricingResponse,
    ResourceType,
    UsageEventCreate,
    UsageEventResponse,
    UsageSummary,
    estimate_cost,
    generate_invoice,
    get_usage_summary,
    record_usage,
)

logger = logging.getLogger(__name__)

router = APIRouter()


def get_tenant_id() -> str:
    """Get current tenant ID (stub for auth integration)."""
    return "tenant_default"


def get_user_id() -> str:
    """Get current user ID (stub for auth integration)."""
    return "user_default"


@router.post("/usage", response_model=UsageEventResponse)
async def create_usage_event(
    event: UsageEventCreate,
    tenant_id: str = Depends(get_tenant_id),
    user_id: str = Depends(get_user_id),
):
    """Record a usage event."""
    usage_event = record_usage(
        tenant_id=tenant_id,
        user_id=user_id,
        resource_type=event.resource_type,
        quantity=event.quantity,
        metadata=event.metadata,
    )

    return UsageEventResponse(
        event_id=usage_event.event_id,
        tenant_id=usage_event.tenant_id,
        user_id=usage_event.user_id,
        resource_type=usage_event.resource_type,
        quantity=usage_event.quantity,
        unit_price=usage_event.unit_price,
        total_price=usage_event.total_price,
        timestamp=usage_event.timestamp.isoformat(),
    )


@router.get("/usage/summary", response_model=UsageSummary)
async def get_usage_summary_endpoint(
    period: str = Query(default="month", pattern="^(day|week|month|year)$"),
    tenant_id: str = Depends(get_tenant_id),
):
    """Get usage summary for a billing period."""
    now = datetime.now(UTC)

    if period == "day":
        period_start = now - timedelta(days=1)
    elif period == "week":
        period_start = now - timedelta(weeks=1)
    elif period == "month":
        period_start = now - timedelta(days=30)
    else:
        period_start = now - timedelta(days=365)

    return get_usage_summary(tenant_id, period_start, now)


@router.get("/pricing", response_model=list[PricingResponse])
async def get_pricing():
    """Get current pricing for all resources."""
    from .models import PRICING

    units = {
        ResourceType.API_CALL: "call",
        ResourceType.JOB_SUBMISSION: "job",
        ResourceType.QUANTUM_SHOT: "shot",
        ResourceType.COMPUTE_TIME: "second",
        ResourceType.STORAGE: "MB-hour",
        ResourceType.KEY_GENERATION: "key",
        ResourceType.WEBHOOK_CALL: "call",
    }

    return [
        PricingResponse(
            resource_type=rt.value,
            unit=units.get(rt, "unit"),
            price_usd=price,
        )
        for rt, price in PRICING.items()
    ]


@router.post("/estimate", response_model=CostEstimateResponse)
async def estimate_job_cost(request: CostEstimateRequest):
    """Estimate cost for a job configuration."""
    return estimate_cost(
        shots=request.shots,
        jobs=request.jobs,
        compute_seconds=request.compute_seconds,
        storage_mb_hours=request.storage_mb_hours,
    )


@router.post("/invoices/generate", response_model=InvoiceResponse)
async def generate_invoice_endpoint(
    period: str = Query(default="month", pattern="^(week|month)$"),
    tenant_id: str = Depends(get_tenant_id),
):
    """Generate an invoice for the billing period."""
    now = datetime.now(UTC)

    if period == "week":
        period_start = now - timedelta(weeks=1)
    else:
        period_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    invoice = generate_invoice(tenant_id, period_start, now)

    return InvoiceResponse(
        invoice_id=invoice.invoice_id,
        tenant_id=invoice.tenant_id,
        period_start=invoice.period_start.isoformat(),
        period_end=invoice.period_end.isoformat(),
        status=invoice.status,
        subtotal=invoice.subtotal,
        tax=invoice.tax,
        total=invoice.total,
        line_items=[
            {
                "resource_type": item.resource_type.value,
                "quantity": item.quantity,
                "unit_price": item.unit_price,
                "total_price": item.total_price,
            }
            for item in invoice.line_items
        ],
        created_at=invoice.created_at.isoformat(),
        paid_at=invoice.paid_at.isoformat() if invoice.paid_at else None,
        payment_url=f"https://billing.example.com/pay/{invoice.invoice_id}",
    )


@router.get("/invoices", response_model=list[InvoiceResponse])
async def list_invoices(
    tenant_id: str = Depends(get_tenant_id),
    limit: int = Query(default=10, le=100),
):
    """List invoices for the tenant."""
    from .models import _invoices

    tenant_invoices = _invoices.get(tenant_id, [])

    return [
        InvoiceResponse(
            invoice_id=inv.invoice_id,
            tenant_id=inv.tenant_id,
            period_start=inv.period_start.isoformat(),
            period_end=inv.period_end.isoformat(),
            status=inv.status,
            subtotal=inv.subtotal,
            tax=inv.tax,
            total=inv.total,
            line_items=[
                {
                    "resource_type": item.resource_type.value,
                    "quantity": item.quantity,
                    "unit_price": item.unit_price,
                    "total_price": item.total_price,
                }
                for item in inv.line_items
            ],
            created_at=inv.created_at.isoformat(),
            paid_at=inv.paid_at.isoformat() if inv.paid_at else None,
            payment_url=f"https://billing.example.com/pay/{inv.invoice_id}",
        )
        for inv in tenant_invoices[:limit]
    ]
