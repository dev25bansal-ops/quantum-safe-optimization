"""
Webhook service with HMAC signature verification and retry logic.

Features:
- HMAC-SHA256 signature for webhook verification
- Exponential backoff retry logic
- Multiple event types support
- Async delivery with configurable timeouts
- Webhook registration and management
"""

import asyncio
import hashlib
import hmac
import ipaddress
import json
import os
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any
from urllib.parse import urlparse

import httpx

# Configuration
WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET", "quantum-webhook-secret-change-in-production")
WEBHOOK_TIMEOUT = float(os.getenv("WEBHOOK_TIMEOUT", "30"))
WEBHOOK_MAX_RETRIES = int(os.getenv("WEBHOOK_MAX_RETRIES", "3"))
WEBHOOK_RETRY_BASE_DELAY = float(os.getenv("WEBHOOK_RETRY_BASE_DELAY", "1.0"))
WEBHOOK_RETRY_MAX_DELAY = float(os.getenv("WEBHOOK_RETRY_MAX_DELAY", "60.0"))
WEBHOOK_ALLOWED_HOSTS = os.getenv("WEBHOOK_ALLOWED_HOSTS", "")
WEBHOOK_BLOCK_PRIVATE = os.getenv("WEBHOOK_BLOCK_PRIVATE", "true").lower() == "true"
WEBHOOK_REQUIRE_HTTPS = os.getenv("WEBHOOK_REQUIRE_HTTPS", "true").lower() == "true"
WEBHOOK_ALLOWLIST_ONLY = os.getenv("WEBHOOK_ALLOWLIST_ONLY", "false").lower() == "true"


def _host_matches_allowlist(host: str, allowlist: list[str]) -> bool:
    """Check if host matches any allowlist entry (exact or suffix)."""
    for allowed in allowlist:
        allowed = allowed.strip().lower()
        if not allowed:
            continue
        if host == allowed or host.endswith(f".{allowed}"):
            return True
    return False


def _is_blocked_hostname(host: str) -> bool:
    """Basic hostname blocklist for local/internal targets."""
    blocked = {"localhost", "127.0.0.1", "::1", "0.0.0.0"}  # noqa: S104 - Localhost bindings
    if host in blocked:
        return True
    if host.endswith(".local") or host.endswith(".internal"):
        return True
    return False


def _is_private_ip(host: str) -> bool:
    """Check if host is a private or otherwise non-public IP address."""
    try:
        ip = ipaddress.ip_address(host)
        return any(
            [
                ip.is_private,
                ip.is_loopback,
                ip.is_link_local,
                ip.is_multicast,
                ip.is_reserved,
            ]
        )
    except ValueError:
        return False


def validate_webhook_url(url: str) -> tuple[bool, str]:
    """
    Validate webhook destination URL to mitigate SSRF.

    Rules:
    - Must be http/https
    - HTTPS required by default (unless DEMO_MODE=true)
    - No credentials in URL
    - Block localhost/private IPs (configurable)
    - Block cloud metadata endpoints
    - Enforce allowlist when configured
    """
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        return False, "invalid scheme"

    demo_mode = os.getenv("DEMO_MODE", "false").lower() == "true"
    if WEBHOOK_REQUIRE_HTTPS and not demo_mode and parsed.scheme != "https":
        return False, "https required"

    if parsed.username or parsed.password:
        return False, "credentials not allowed in URL"

    host = (parsed.hostname or "").lower()
    if not host:
        return False, "missing hostname"

    if _is_blocked_hostname(host):
        return False, "local/internal hostname not allowed"

    # Block cloud metadata endpoints (SSRF protection)
    blocked_metadata_endpoints = {
        "169.254.169.254",  # AWS IMDS
        "metadata.google.internal",  # GCP
        "169.254.169.253",  # Azure IMDS
        "100.100.100.200",  # Aliyun
    }

    if host in blocked_metadata_endpoints:
        return False, "cloud metadata endpoint not allowed"

    if WEBHOOK_BLOCK_PRIVATE and _is_private_ip(host):
        return False, "private IP not allowed"

    allowlist = [h for h in WEBHOOK_ALLOWED_HOSTS.split(",") if h.strip()]
    if allowlist:
        if not _host_matches_allowlist(host, allowlist):
            return False, "hostname not in allowlist"
    elif WEBHOOK_ALLOWLIST_ONLY:
        return False, "allowlist required"

    return True, ""


class WebhookEvent(str, Enum):
    """Webhook event types."""

    JOB_CREATED = "job.created"
    JOB_STARTED = "job.started"
    JOB_PROGRESS = "job.progress"
    JOB_COMPLETED = "job.completed"
    JOB_FAILED = "job.failed"
    JOB_CANCELLED = "job.cancelled"

    # Security events
    KEY_GENERATED = "security.key_generated"
    KEY_ROTATED = "security.key_rotated"
    ENCRYPTION_COMPLETED = "security.encryption_completed"


@dataclass
class WebhookDeliveryResult:
    """Result of a webhook delivery attempt."""

    success: bool
    status_code: int | None = None
    response_body: str | None = None
    error: str | None = None
    attempts: int = 1
    delivered_at: datetime | None = None
    retry_after: datetime | None = None


@dataclass
class WebhookPayload:
    """Webhook payload with metadata."""

    event: WebhookEvent
    job_id: str
    timestamp: datetime = field(default_factory=datetime.utcnow)
    data: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "event": self.event.value,
            "job_id": self.job_id,
            "timestamp": self.timestamp.isoformat(),
            "data": self.data,
        }

    def to_json(self) -> str:
        """Convert to JSON string."""
        return json.dumps(self.to_dict(), default=str)


class WebhookSigner:
    """HMAC-SHA256 signer for webhook payloads."""

    def __init__(self, secret: str = WEBHOOK_SECRET):
        self.secret = secret.encode("utf-8")

    def sign(self, payload: str, timestamp: str) -> str:
        """
        Generate HMAC-SHA256 signature for payload.

        Args:
            payload: JSON payload string
            timestamp: ISO timestamp string

        Returns:
            Hexadecimal signature string
        """
        # Create signing string: timestamp.payload
        signing_string = f"{timestamp}.{payload}"

        signature = hmac.new(
            self.secret, signing_string.encode("utf-8"), hashlib.sha256
        ).hexdigest()

        return signature

    def verify(
        self,
        payload: str,
        timestamp: str,
        signature: str,
        max_age_seconds: int = 300,
    ) -> bool:
        """
        Verify webhook signature.

        Args:
            payload: JSON payload string
            timestamp: ISO timestamp string
            signature: Signature to verify
            max_age_seconds: Maximum age of the timestamp (default 5 minutes)

        Returns:
            True if signature is valid
        """
        # Check timestamp freshness
        try:
            ts = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
            age = (datetime.utcnow() - ts.replace(tzinfo=None)).total_seconds()
            if abs(age) > max_age_seconds:
                return False
        except Exception:
            return False

        # Verify signature
        expected = self.sign(payload, timestamp)
        return hmac.compare_digest(signature, expected)


class WebhookDeliveryService:
    """
    Async webhook delivery service with retry logic.

    Features:
    - Exponential backoff retries
    - HMAC signature headers
    - Configurable timeouts
    - Delivery tracking
    """

    def __init__(
        self,
        signer: WebhookSigner | None = None,
        max_retries: int = WEBHOOK_MAX_RETRIES,
        timeout: float = WEBHOOK_TIMEOUT,
        base_delay: float = WEBHOOK_RETRY_BASE_DELAY,
        max_delay: float = WEBHOOK_RETRY_MAX_DELAY,
    ):
        self.signer = signer or WebhookSigner()
        self.max_retries = max_retries
        self.timeout = timeout
        self.base_delay = base_delay
        self.max_delay = max_delay

        # Delivery statistics
        self._total_deliveries = 0
        self._successful_deliveries = 0
        self._failed_deliveries = 0
        self._total_retries = 0

    def _calculate_delay(self, attempt: int) -> float:
        """Calculate exponential backoff delay with jitter."""
        import random

        # Exponential backoff: base_delay * 2^(attempt-1)
        delay = self.base_delay * (2 ** (attempt - 1))

        # Add jitter (±25%)
        jitter = delay * 0.25 * (2 * random.random() - 1)
        delay += jitter

        # Cap at max delay
        return min(delay, self.max_delay)

    def _build_headers(
        self,
        payload: WebhookPayload,
        payload_json: str,
    ) -> dict[str, str]:
        """Build webhook request headers with signature."""
        timestamp = payload.timestamp.isoformat()
        signature = self.signer.sign(payload_json, timestamp)

        return {
            "Content-Type": "application/json",
            "X-Webhook-Event": payload.event.value,
            "X-Webhook-Timestamp": timestamp,
            "X-Webhook-Signature": f"sha256={signature}",
            "X-Job-ID": payload.job_id,
            "X-Webhook-Version": "1.0",
        }

    async def deliver(
        self,
        url: str,
        payload: WebhookPayload,
        retry: bool = True,
    ) -> WebhookDeliveryResult:
        """
        Deliver webhook to URL with optional retries.

        Args:
            url: Destination URL
            payload: Webhook payload
            retry: Whether to retry on failure

        Returns:
            WebhookDeliveryResult with delivery status
        """
        is_valid, error = validate_webhook_url(url)
        if not is_valid:
            return WebhookDeliveryResult(
                success=False,
                error=f"Webhook URL rejected: {error}",
                attempts=1,
                delivered_at=datetime.utcnow(),
            )

        self._total_deliveries += 1
        payload_json = payload.to_json()
        headers = self._build_headers(payload, payload_json)

        max_attempts = self.max_retries + 1 if retry else 1
        last_error: str | None = None
        last_status: int | None = None

        for attempt in range(1, max_attempts + 1):
            try:
                async with httpx.AsyncClient(timeout=self.timeout) as client:
                    response = await client.post(
                        url,
                        content=payload_json,
                        headers=headers,
                    )

                    last_status = response.status_code

                    if response.status_code < 400:
                        self._successful_deliveries += 1
                        return WebhookDeliveryResult(
                            success=True,
                            status_code=response.status_code,
                            response_body=response.text[:500],  # Truncate response
                            attempts=attempt,
                            delivered_at=datetime.utcnow(),
                        )

                    # 4xx errors (except 429) should not be retried
                    if 400 <= response.status_code < 500 and response.status_code != 429:
                        last_error = f"Client error: {response.status_code}"
                        break

                    last_error = f"Server error: {response.status_code}"

            except httpx.TimeoutException:
                last_error = "Request timeout"
            except httpx.ConnectError:
                last_error = "Connection error"
            except Exception as e:
                last_error = str(e)

            # Retry logic
            if attempt < max_attempts:
                self._total_retries += 1
                delay = self._calculate_delay(attempt)
                await asyncio.sleep(delay)

        # All attempts failed
        self._failed_deliveries += 1
        return WebhookDeliveryResult(
            success=False,
            status_code=last_status,
            error=last_error,
            attempts=max_attempts,
            retry_after=datetime.utcnow() + timedelta(minutes=5),
        )

    async def deliver_batch(
        self,
        urls: list[str],
        payload: WebhookPayload,
    ) -> dict[str, WebhookDeliveryResult]:
        """
        Deliver webhook to multiple URLs concurrently.

        Args:
            urls: List of destination URLs
            payload: Webhook payload

        Returns:
            Dictionary mapping URL to delivery result
        """
        tasks = [self.deliver(url, payload) for url in urls]

        results = await asyncio.gather(*tasks, return_exceptions=True)

        return {
            url: result
            if isinstance(result, WebhookDeliveryResult)
            else WebhookDeliveryResult(success=False, error=str(result))
            for url, result in zip(urls, results, strict=False)
        }

    def get_statistics(self) -> dict[str, Any]:
        """Get delivery statistics."""
        total = self._total_deliveries or 1  # Avoid division by zero
        return {
            "total_deliveries": self._total_deliveries,
            "successful_deliveries": self._successful_deliveries,
            "failed_deliveries": self._failed_deliveries,
            "total_retries": self._total_retries,
            "success_rate": self._successful_deliveries / total,
            "retry_rate": self._total_retries / total if self._total_deliveries else 0,
        }


# Global webhook service instance
webhook_service = WebhookDeliveryService()


# Convenience functions
async def send_job_webhook(
    callback_url: str,
    job_id: str,
    event: WebhookEvent,
    data: dict[str, Any] | None = None,
) -> WebhookDeliveryResult:
    """
    Send a job-related webhook notification.

    Args:
        callback_url: Destination URL
        job_id: Job identifier
        event: Webhook event type
        data: Additional event data

    Returns:
        WebhookDeliveryResult
    """
    payload = WebhookPayload(
        event=event,
        job_id=job_id,
        data=data or {},
    )

    return await webhook_service.deliver(callback_url, payload)


async def send_job_completed_webhook(
    callback_url: str,
    job_id: str,
    result: dict[str, Any],
    status: str = "completed",
) -> WebhookDeliveryResult:
    """
    Send job completion webhook (backward compatible).

    Args:
        callback_url: Destination URL
        job_id: Job identifier
        result: Job result data
        status: Job status

    Returns:
        WebhookDeliveryResult
    """
    event = WebhookEvent.JOB_COMPLETED if status == "completed" else WebhookEvent.JOB_FAILED

    return await send_job_webhook(
        callback_url=callback_url,
        job_id=job_id,
        event=event,
        data={"result": result, "status": status},
    )


async def send_job_failed_webhook(
    callback_url: str,
    job_id: str,
    error: str,
) -> WebhookDeliveryResult:
    """
    Send job failure webhook.

    Args:
        callback_url: Destination URL
        job_id: Job identifier
        error: Error message

    Returns:
        WebhookDeliveryResult
    """
    return await send_job_webhook(
        callback_url=callback_url,
        job_id=job_id,
        event=WebhookEvent.JOB_FAILED,
        data={"error": error, "status": "failed"},
    )


def verify_webhook_signature(
    payload: str,
    timestamp: str,
    signature: str,
    secret: str | None = None,
) -> bool:
    """
    Verify an incoming webhook signature.

    This function is intended for webhook receivers to verify
    that the webhook was sent by the Quantum platform.

    Args:
        payload: Raw JSON payload string
        timestamp: X-Webhook-Timestamp header value
        signature: X-Webhook-Signature header value (with "sha256=" prefix)
        secret: Webhook secret (uses default if not provided)

    Returns:
        True if signature is valid
    """
    # Strip "sha256=" prefix if present
    if signature.startswith("sha256="):
        signature = signature[7:]

    signer = WebhookSigner(secret or WEBHOOK_SECRET)
    return signer.verify(payload, timestamp, signature)
