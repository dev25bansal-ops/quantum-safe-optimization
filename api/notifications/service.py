"""
Notification Service.

Provides real-time notifications via WebSocket, email, and webhooks.
"""

import asyncio
import json
import os
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional
from uuid import uuid4

import structlog

logger = structlog.get_logger()


class NotificationType(str, Enum):
    JOB_COMPLETED = "job_completed"
    JOB_FAILED = "job_failed"
    JOB_STARTED = "job_started"
    KEY_ROTATED = "key_rotated"
    KEY_EXPIRING = "key_expiring"
    BILLING_ALERT = "billing_alert"
    INVOICE_GENERATED = "invoice_generated"
    QUOTA_WARNING = "quota_warning"
    SECURITY_ALERT = "security_alert"
    SYSTEM_MAINTENANCE = "system_maintenance"
    ALGORITHM_UPDATED = "algorithm_updated"
    MARKETPLACE_PURCHASE = "marketplace_purchase"


class NotificationPriority(str, Enum):
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    URGENT = "urgent"


@dataclass
class Notification:
    notification_id: str
    notification_type: NotificationType
    title: str
    message: str
    user_id: str
    tenant_id: Optional[str] = None
    priority: NotificationPriority = NotificationPriority.NORMAL
    data: dict[str, Any] = field(default_factory=dict)
    read: bool = False
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    read_at: Optional[datetime] = None
    expires_at: Optional[datetime] = None

    def to_dict(self) -> dict:
        return {
            "notification_id": self.notification_id,
            "notification_type": self.notification_type.value,
            "title": self.title,
            "message": self.message,
            "user_id": self.user_id,
            "tenant_id": self.tenant_id,
            "priority": self.priority.value,
            "data": self.data,
            "read": self.read,
            "created_at": self.created_at.isoformat(),
            "read_at": self.read_at.isoformat() if self.read_at else None,
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
        }


class NotificationStore:
    """In-memory notification storage."""

    def __init__(self, max_notifications_per_user: int = 1000):
        self._notifications: dict[str, list[Notification]] = {}
        self._max_per_user = max_notifications_per_user
        self._lock = asyncio.Lock()

    async def add(self, notification: Notification) -> None:
        """Add a notification."""
        async with self._lock:
            user_id = notification.user_id
            if user_id not in self._notifications:
                self._notifications[user_id] = []

            self._notifications[user_id].insert(0, notification)

            if len(self._notifications[user_id]) > self._max_per_user:
                self._notifications[user_id] = self._notifications[user_id][: self._max_per_user]

    async def get_user_notifications(
        self,
        user_id: str,
        unread_only: bool = False,
        limit: int = 50,
    ) -> list[Notification]:
        """Get notifications for a user."""
        async with self._lock:
            notifications = self._notifications.get(user_id, [])

            if unread_only:
                notifications = [n for n in notifications if not n.read]

            return notifications[:limit]

    async def mark_read(self, user_id: str, notification_id: str) -> bool:
        """Mark notification as read."""
        async with self._lock:
            for notification in self._notifications.get(user_id, []):
                if notification.notification_id == notification_id:
                    notification.read = True
                    notification.read_at = datetime.now(timezone.utc)
                    return True
            return False

    async def mark_all_read(self, user_id: str) -> int:
        """Mark all notifications as read for a user."""
        async with self._lock:
            count = 0
            for notification in self._notifications.get(user_id, []):
                if not notification.read:
                    notification.read = True
                    notification.read_at = datetime.now(timezone.utc)
                    count += 1
            return count

    async def delete(self, user_id: str, notification_id: str) -> bool:
        """Delete a notification."""
        async with self._lock:
            if user_id not in self._notifications:
                return False

            original_len = len(self._notifications[user_id])
            self._notifications[user_id] = [
                n for n in self._notifications[user_id] if n.notification_id != notification_id
            ]
            return len(self._notifications[user_id]) < original_len

    async def get_unread_count(self, user_id: str) -> int:
        """Get unread notification count."""
        async with self._lock:
            return sum(1 for n in self._notifications.get(user_id, []) if not n.read)


class NotificationService:
    """Service for sending notifications."""

    def __init__(self):
        self._store = NotificationStore()
        self._websocket_clients: dict[str, list[Any]] = {}
        self._webhook_urls: dict[str, list[str]] = {}

    def register_websocket(self, user_id: str, websocket: Any) -> None:
        """Register a WebSocket client."""
        if user_id not in self._websocket_clients:
            self._websocket_clients[user_id] = []
        self._websocket_clients[user_id].append(websocket)

    def unregister_websocket(self, user_id: str, websocket: Any) -> None:
        """Unregister a WebSocket client."""
        if user_id in self._websocket_clients:
            try:
                self._websocket_clients[user_id].remove(websocket)
            except ValueError:
                pass

    async def send(
        self,
        notification_type: NotificationType,
        title: str,
        message: str,
        user_id: str,
        tenant_id: Optional[str] = None,
        priority: NotificationPriority = NotificationPriority.NORMAL,
        data: Optional[dict[str, Any]] = None,
        push: bool = True,
    ) -> Notification:
        """Send a notification."""
        notification = Notification(
            notification_id=f"notif_{uuid4().hex[:12]}",
            notification_type=notification_type,
            title=title,
            message=message,
            user_id=user_id,
            tenant_id=tenant_id,
            priority=priority,
            data=data or {},
        )

        await self._store.add(notification)

        if push:
            await self._push_notification(notification)

        logger.info(
            "notification_sent",
            notification_id=notification.notification_id,
            type=notification_type.value,
            user_id=user_id,
        )

        return notification

    async def _push_notification(self, notification: Notification) -> None:
        """Push notification to connected clients."""
        user_id = notification.user_id
        message = json.dumps(
            {
                "type": "notification",
                "data": notification.to_dict(),
            }
        )

        if user_id in self._websocket_clients:
            for ws in self._websocket_clients[user_id]:
                try:
                    await ws.send_text(message)
                except Exception as e:
                    logger.warning("websocket_push_failed", error=str(e))

    async def get_notifications(
        self,
        user_id: str,
        unread_only: bool = False,
        limit: int = 50,
    ) -> list[dict]:
        """Get notifications for a user."""
        notifications = await self._store.get_user_notifications(user_id, unread_only, limit)
        return [n.to_dict() for n in notifications]

    async def mark_read(self, user_id: str, notification_id: str) -> bool:
        """Mark notification as read."""
        return await self._store.mark_read(user_id, notification_id)

    async def mark_all_read(self, user_id: str) -> int:
        """Mark all notifications as read."""
        return await self._store.mark_all_read(user_id)

    async def get_unread_count(self, user_id: str) -> int:
        """Get unread notification count."""
        return await self._store.get_unread_count(user_id)

    async def job_completed(
        self,
        user_id: str,
        job_id: str,
        job_name: str,
        result_summary: str,
    ) -> Notification:
        """Send job completion notification."""
        return await self.send(
            notification_type=NotificationType.JOB_COMPLETED,
            title="Job Completed",
            message=f"Your job '{job_name}' has completed. {result_summary}",
            user_id=user_id,
            data={"job_id": job_id},
        )

    async def job_failed(
        self,
        user_id: str,
        job_id: str,
        job_name: str,
        error: str,
    ) -> Notification:
        """Send job failure notification."""
        return await self.send(
            notification_type=NotificationType.JOB_FAILED,
            title="Job Failed",
            message=f"Your job '{job_name}' failed: {error}",
            user_id=user_id,
            priority=NotificationPriority.HIGH,
            data={"job_id": job_id, "error": error},
        )

    async def quota_warning(
        self,
        user_id: str,
        tenant_id: str,
        resource: str,
        usage_percent: float,
    ) -> Notification:
        """Send quota warning notification."""
        return await self.send(
            notification_type=NotificationType.QUOTA_WARNING,
            title="Quota Warning",
            message=f"You've used {usage_percent:.0f}% of your {resource} quota.",
            user_id=user_id,
            tenant_id=tenant_id,
            priority=NotificationPriority.HIGH,
            data={"resource": resource, "usage_percent": usage_percent},
        )

    async def key_expiring(
        self,
        user_id: str,
        key_id: str,
        days_remaining: int,
    ) -> Notification:
        """Send key expiration warning."""
        return await self.send(
            notification_type=NotificationType.KEY_EXPIRING,
            title="Key Expiring Soon",
            message=f"Your key will expire in {days_remaining} days.",
            user_id=user_id,
            priority=NotificationPriority.HIGH
            if days_remaining <= 7
            else NotificationPriority.NORMAL,
            data={"key_id": key_id, "days_remaining": days_remaining},
        )

    async def billing_alert(
        self,
        user_id: str,
        tenant_id: str,
        message: str,
        amount: float,
    ) -> Notification:
        """Send billing alert."""
        return await self.send(
            notification_type=NotificationType.BILLING_ALERT,
            title="Billing Alert",
            message=message,
            user_id=user_id,
            tenant_id=tenant_id,
            priority=NotificationPriority.HIGH,
            data={"amount": amount},
        )

    async def security_alert(
        self,
        user_id: str,
        tenant_id: str,
        message: str,
        severity: str,
    ) -> Notification:
        """Send security alert."""
        priority = (
            NotificationPriority.URGENT if severity == "critical" else NotificationPriority.HIGH
        )
        return await self.send(
            notification_type=NotificationType.SECURITY_ALERT,
            title="Security Alert",
            message=message,
            user_id=user_id,
            tenant_id=tenant_id,
            priority=priority,
            data={"severity": severity},
        )


notification_service = NotificationService()
