"""
Security Dashboard Module.

Provides comprehensive security monitoring, alerting, and compliance
tracking for the quantum optimization platform, including real-time
security event monitoring, threat detection, and compliance reporting.
"""

import logging
from typing import Any, Dict, List, Optional, Tuple
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime, timedelta
from collections import defaultdict, Counter
import json

logger = logging.getLogger(__name__)


class SecurityEventType(Enum):
    """Types of security events."""
    AUTHENTICATION_SUCCESS = "authentication_success"
    AUTHENTICATION_FAILURE = "authentication_failure"
    AUTHORIZATION_FAILURE = "authorization_failure"
    RATE_LIMIT_EXCEEDED = "rate_limit_exceeded"
    MALICIOUS_INPUT_DETECTED = "malicious_input_detected"
    SQL_INJECTION_ATTEMPT = "sql_injection_attempt"
    XSS_ATTEMPT = "xss_attempt"
    COMMAND_INJECTION_ATTEMPT = "command_injection_attempt"
    SUSPICIOUS_ACTIVITY = "suspicious_activity"
    DATA_ACCESS = "data_access"
    DATA_MODIFICATION = "data_modification"
    CONFIGURATION_CHANGE = "configuration_change"
    SECURITY_VIOLATION = "security_violation"


class SecuritySeverity(Enum):
    """Security event severity levels."""
    INFO = "info"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class ComplianceStatus(Enum):
    """Compliance status."""
    COMPLIANT = "compliant"
    NON_COMPLIANT = "non_compliant"
    PENDING_REVIEW = "pending_review"
    UNKNOWN = "unknown"


@dataclass
class SecurityEvent:
    """Represents a security event."""
    
    event_id: str
    event_type: SecurityEventType
    severity: SecuritySeverity
    timestamp: datetime = field(default_factory=datetime.now)
    user_id: Optional[str] = None
    ip_address: Optional[str] = None
    resource: Optional[str] = None
    details: Dict[str, Any] = field(default_factory=dict)
    resolved: bool = False
    resolved_at: Optional[datetime] = None
    resolved_by: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "event_id": self.event_id,
            "event_type": self.event_type.value,
            "severity": self.severity.value,
            "timestamp": self.timestamp.isoformat(),
            "user_id": self.user_id,
            "ip_address": self.ip_address,
            "resource": self.resource,
            "details": self.details,
            "resolved": self.resolved,
            "resolved_at": self.resolved_at.isoformat() if self.resolved_at else None,
            "resolved_by": self.resolved_by,
        }


@dataclass
class SecurityAlert:
    """Represents a security alert."""
    
    alert_id: str
    title: str
    description: str
    severity: SecuritySeverity
    created_at: datetime = field(default_factory=datetime.now)
    events: List[str] = field(default_factory=list)  # event IDs
    status: str = "open"  # open, investigating, resolved, dismissed
    assigned_to: Optional[str] = None
    resolved_at: Optional[datetime] = None
    resolution_notes: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "alert_id": self.alert_id,
            "title": self.title,
            "description": self.description,
            "severity": self.severity.value,
            "created_at": self.created_at.isoformat(),
            "events": self.events,
            "status": self.status,
            "assigned_to": self.assigned_to,
            "resolved_at": self.resolved_at.isoformat() if self.resolved_at else None,
            "resolution_notes": self.resolution_notes,
        }


@dataclass
class ComplianceCheck:
    """Represents a compliance check."""
    
    check_id: str
    name: str
    description: str
    status: ComplianceStatus
    last_checked: datetime = field(default_factory=datetime.now)
    details: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "check_id": self.check_id,
            "name": self.name,
            "description": self.description,
            "status": self.status.value,
            "last_checked": self.last_checked.isoformat(),
            "details": self.details,
        }


class SecurityDashboard:
    """Main security dashboard for monitoring and alerting."""
    
    def __init__(self, max_events: int = 10000, max_alerts: int = 1000):
        self.max_events = max_events
        self.max_alerts = max_alerts
        
        # Event storage
        self._events: List[SecurityEvent] = []
        self._events_by_user: Dict[str, List[SecurityEvent]] = defaultdict(list)
        self._events_by_type: Dict[SecurityEventType, List[SecurityEvent]] = defaultdict(list)
        
        # Alert storage
        self._alerts: List[SecurityAlert] = []
        self._alerts_by_severity: Dict[SecuritySeverity, List[SecurityAlert]] = defaultdict(list)
        
        # Compliance checks
        self._compliance_checks: Dict[str, ComplianceCheck] = {}
        
        # Statistics
        self._statistics: Dict[str, Any] = {
            "total_events": 0,
            "total_alerts": 0,
            "resolved_events": 0,
            "resolved_alerts": 0,
        }
        
        # Threat detection rules
        self._threat_rules: List[Callable] = []
    
    def log_event(
        self,
        event_type: SecurityEventType,
        severity: SecuritySeverity,
        user_id: Optional[str] = None,
        ip_address: Optional[str] = None,
        resource: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None
    ) -> SecurityEvent:
        """Log a security event."""
        
        # Create event
        event = SecurityEvent(
            event_id=self._generate_event_id(),
            event_type=event_type,
            severity=severity,
            user_id=user_id,
            ip_address=ip_address,
            resource=resource,
            details=details or {}
        )
        
        # Add to storage
        self._events.append(event)
        self._events_by_user[user_id].append(event) if user_id else None
        self._events_by_type[event_type].append(event)
        
        # Enforce max events limit
        if len(self._events) > self.max_events:
            removed = self._events.pop(0)
            # Clean up indexes
            if removed.user_id and removed.user_id in self._events_by_user:
                self._events_by_user[removed.user_id] = [
                    e for e in self._events_by_user[removed.user_id]
                    if e.event_id != removed.event_id
                ]
        
        # Update statistics
        self._statistics["total_events"] += 1
        
        # Check for threats
        self._check_for_threats(event)
        
        # Log based on severity
        if severity == SecuritySeverity.CRITICAL:
            logger.critical(f"Security event: {event_type.value}", extra=event.to_dict())
        elif severity == SecuritySeverity.HIGH:
            logger.error(f"Security event: {event_type.value}", extra=event.to_dict())
        elif severity == SecuritySeverity.MEDIUM:
            logger.warning(f"Security event: {event_type.value}", extra=event.to_dict())
        else:
            logger.info(f"Security event: {event_type.value}", extra=event.to_dict())
        
        return event
    
    def get_event(self, event_id: str) -> Optional[SecurityEvent]:
        """Get a security event by ID."""
        for event in self._events:
            if event.event_id == event_id:
                return event
        return None
    
    def get_events(
        self,
        event_type: Optional[SecurityEventType] = None,
        severity: Optional[SecuritySeverity] = None,
        user_id: Optional[str] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        limit: int = 100
    ) -> List[SecurityEvent]:
        """Get security events with filters."""
        events = self._events
        
        # Apply filters
        if event_type:
            events = [e for e in events if e.event_type == event_type]
        
        if severity:
            events = [e for e in events if e.severity == severity]
        
        if user_id:
            events = [e for e in events if e.user_id == user_id]
        
        if start_time:
            events = [e for e in events if e.timestamp >= start_time]
        
        if end_time:
            events = [e for e in events if e.timestamp <= end_time]
        
        # Sort by timestamp (newest first)
        events.sort(key=lambda e: e.timestamp, reverse=True)
        
        # Apply limit
        return events[:limit]
    
    def get_user_events(self, user_id: str, limit: int = 100) -> List[SecurityEvent]:
        """Get events for a specific user."""
        events = self._events_by_user.get(user_id, [])
        events.sort(key=lambda e: e.timestamp, reverse=True)
        return events[:limit]
    
    def resolve_event(
        self,
        event_id: str,
        resolved_by: str
    ) -> bool:
        """Mark a security event as resolved."""
        event = self.get_event(event_id)
        if event is None:
            return False
        
        event.resolved = True
        event.resolved_at = datetime.now()
        event.resolved_by = resolved_by
        
        self._statistics["resolved_events"] += 1
        
        logger.info(f"Resolved security event: {event_id}")
        
        return True
    
    def create_alert(
        self,
        title: str,
        description: str,
        severity: SecuritySeverity,
        event_ids: Optional[List[str]] = None
    ) -> SecurityAlert:
        """Create a security alert."""
        
        alert = SecurityAlert(
            alert_id=self._generate_alert_id(),
            title=title,
            description=description,
            severity=severity,
            events=event_ids or []
        )
        
        # Add to storage
        self._alerts.append(alert)
        self._alerts_by_severity[severity].append(alert)
        
        # Enforce max alerts limit
        if len(self._alerts) > self.max_alerts:
            removed = self._alerts.pop(0)
            if removed.severity in self._alerts_by_severity:
                self._alerts_by_severity[removed.severity] = [
                    a for a in self._alerts_by_severity[removed.severity]
                    if a.alert_id != removed.alert_id
                ]
        
        # Update statistics
        self._statistics["total_alerts"] += 1
        
        logger.warning(f"Security alert created: {title} ({severity.value})")
        
        return alert
    
    def get_alert(self, alert_id: str) -> Optional[SecurityAlert]:
        """Get a security alert by ID."""
        for alert in self._alerts:
            if alert.alert_id == alert_id:
                return alert
        return None
    
    def get_alerts(
        self,
        severity: Optional[SecuritySeverity] = None,
        status: Optional[str] = None,
        limit: int = 100
    ) -> List[SecurityAlert]:
        """Get security alerts with filters."""
        alerts = self._alerts
        
        # Apply filters
        if severity:
            alerts = [a for a in alerts if a.severity == severity]
        
        if status:
            alerts = [a for a in alerts if a.status == status]
        
        # Sort by created_at (newest first)
        alerts.sort(key=lambda a: a.created_at, reverse=True)
        
        # Apply limit
        return alerts[:limit]
    
    def resolve_alert(
        self,
        alert_id: str,
        resolved_by: str,
        resolution_notes: Optional[str] = None
    ) -> bool:
        """Mark a security alert as resolved."""
        alert = self.get_alert(alert_id)
        if alert is None:
            return False
        
        alert.status = "resolved"
        alert.resolved_at = datetime.now()
        alert.resolution_notes = resolution_notes
        
        self._statistics["resolved_alerts"] += 1
        
        logger.info(f"Resolved security alert: {alert_id}")
        
        return True
    
    def add_compliance_check(
        self,
        check_id: str,
        name: str,
        description: str,
        status: ComplianceStatus,
        details: Optional[Dict[str, Any]] = None
    ) -> ComplianceCheck:
        """Add or update a compliance check."""
        
        check = ComplianceCheck(
            check_id=check_id,
            name=name,
            description=description,
            status=status,
            details=details or {}
        )
        
        self._compliance_checks[check_id] = check
        
        logger.info(f"Compliance check added: {name} ({status.value})")
        
        return check
    
    def get_compliance_check(self, check_id: str) -> Optional[ComplianceCheck]:
        """Get a compliance check by ID."""
        return self._compliance_checks.get(check_id)
    
    def get_all_compliance_checks(self) -> List[ComplianceCheck]:
        """Get all compliance checks."""
        return list(self._compliance_checks.values())
    
    def update_compliance_status(
        self,
        check_id: str,
        status: ComplianceStatus,
        details: Optional[Dict[str, Any]] = None
    ) -> bool:
        """Update compliance check status."""
        check = self.get_compliance_check(check_id)
        if check is None:
            return False
        
        check.status = status
        check.last_checked = datetime.now()
        if details:
            check.details.update(details)
        
        logger.info(f"Compliance check updated: {check_id} ({status.value})")
        
        return True
    
    def get_compliance_summary(self) -> Dict[str, Any]:
        """Get compliance summary."""
        checks = self.get_all_compliance_checks()
        
        summary = {
            "total_checks": len(checks),
            "compliant": 0,
            "non_compliant": 0,
            "pending_review": 0,
            "unknown": 0,
            "overall_status": ComplianceStatus.COMPLIANT.value,
        }
        
        for check in checks:
            summary[check.status.value] += 1
        
        # Determine overall status
        if summary["non_compliant"] > 0:
            summary["overall_status"] = ComplianceStatus.NON_COMPLIANT.value
        elif summary["pending_review"] > 0:
            summary["overall_status"] = ComplianceStatus.PENDING_REVIEW.value
        
        return summary
    
    def get_security_statistics(self, time_window: timedelta = timedelta(hours=24)) -> Dict[str, Any]:
        """Get security statistics for a time window."""
        end_time = datetime.now()
        start_time = end_time - time_window
        
        # Get events in time window
        events = self.get_events(start_time=start_time, end_time=end_time, limit=self.max_events)
        
        # Count by type and severity
        events_by_type = Counter(e.event_type.value for e in events)
        events_by_severity = Counter(e.severity.value for e in events)
        
        # Get alerts in time window
        alerts = self.get_alerts(limit=self.max_alerts)
        alerts_in_window = [a for a in alerts if a.created_at >= start_time]
        
        # Count by severity
        alerts_by_severity = Counter(a.severity.value for a in alerts_in_window)
        
        return {
            "time_window": {
                "start": start_time.isoformat(),
                "end": end_time.isoformat(),
                "hours": time_window.total_seconds() / 3600,
            },
            "events": {
                "total": len(events),
                "by_type": dict(events_by_type),
                "by_severity": dict(events_by_severity),
                "resolved": sum(1 for e in events if e.resolved),
            },
            "alerts": {
                "total": len(alerts_in_window),
                "by_severity": dict(alerts_by_severity),
                "open": sum(1 for a in alerts_in_window if a.status == "open"),
                "resolved": sum(1 for a in alerts_in_window if a.status == "resolved"),
            },
            "compliance": self.get_compliance_summary(),
        }
    
    def get_dashboard_data(self) -> Dict[str, Any]:
        """Get complete dashboard data."""
        return {
            "statistics": self.get_security_statistics(),
            "recent_events": [e.to_dict() for e in self.get_events(limit=20)],
            "recent_alerts": [a.to_dict() for a in self.get_alerts(status="open", limit=10)],
            "compliance_checks": [c.to_dict() for c in self.get_all_compliance_checks()],
        }
    
    def _generate_event_id(self) -> str:
        """Generate a unique event ID."""
        return f"evt_{datetime.now().strftime('%Y%m%d%H%M%S')}_{len(self._events)}"
    
    def _generate_alert_id(self) -> str:
        """Generate a unique alert ID."""
        return f"alt_{datetime.now().strftime('%Y%m%d%H%M%S')}_{len(self._alerts)}"
    
    def _check_for_threats(self, event: SecurityEvent) -> None:
        """Check if event indicates a threat."""
        # Check for multiple failed authentications
        if event.event_type == SecurityEventType.AUTHENTICATION_FAILURE:
            user_events = self.get_user_events(event.user_id, limit=10)
            failed_auths = [
                e for e in user_events
                if e.event_type == SecurityEventType.AUTHENTICATION_FAILURE
                and not e.resolved
            ]
            
            if len(failed_auths) >= 5:
                self.create_alert(
                    title="Multiple Failed Authentication Attempts",
                    description=f"User {event.user_id} has {len(failed_auths)} failed authentication attempts",
                    severity=SecuritySeverity.HIGH,
                    event_ids=[e.event_id for e in failed_auths]
                )
        
        # Check for malicious input patterns
        if event.event_type in [
            SecurityEventType.SQL_INJECTION_ATTEMPT,
            SecurityEventType.XSS_ATTEMPT,
            SecurityEventType.COMMAND_INJECTION_ATTEMPT
        ]:
            self.create_alert(
                title=f"{event.event_type.value.replace('_', ' ').title()} Detected",
                description=f"Potential {event.event_type.value} detected from {event.ip_address}",
                severity=SecuritySeverity.CRITICAL,
                event_ids=[event.event_id]
            )
        
        # Check for rate limit violations
        if event.event_type == SecurityEventType.RATE_LIMIT_EXCEEDED:
            recent_events = self.get_events(
                event_type=SecurityEventType.RATE_LIMIT_EXCEEDED,
                start_time=datetime.now() - timedelta(minutes=5),
                limit=100
            )
            
            if len(recent_events) >= 10:
                self.create_alert(
                    title="Excessive Rate Limit Violations",
                    description=f"Multiple rate limit violations detected",
                    severity=SecuritySeverity.HIGH,
                    event_ids=[e.event_id for e in recent_events]
                )
    
    def clear_old_events(self, older_than: timedelta = timedelta(days=30)) -> int:
        """Clear events older than specified time."""
        cutoff_time = datetime.now() - older_than
        
        original_count = len(self._events)
        self._events = [e for e in self._events if e.timestamp > cutoff_time]
        
        # Rebuild indexes
        self._events_by_user = defaultdict(list)
        self._events_by_type = defaultdict(list)
        
        for event in self._events:
            if event.user_id:
                self._events_by_user[event.user_id].append(event)
            self._events_by_type[event.event_type].append(event)
        
        cleared_count = original_count - len(self._events)
        
        logger.info(f"Cleared {cleared_count} old security events")
        
        return cleared_count
    
    def export_events(
        self,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        format: str = "json"
    ) -> str:
        """Export security events."""
        events = self.get_events(start_time=start_time, end_time=end_time, limit=self.max_events)
        
        if format == "json":
            return json.dumps([e.to_dict() for e in events], indent=2)
        else:
            raise ValueError(f"Unsupported format: {format}")


# Factory function
def create_security_dashboard(
    max_events: int = 10000,
    max_alerts: int = 1000
) -> SecurityDashboard:
    """Create a new security dashboard."""
    return SecurityDashboard(max_events, max_alerts)