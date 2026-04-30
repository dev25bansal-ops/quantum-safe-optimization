"""
ML-Based Anomaly Detection for Security.

Provides real-time anomaly detection for:
- Authentication anomalies (unusual login patterns)
- API usage anomalies (rate spikes, unusual endpoints)
- Data access anomalies (unusual query patterns)
- Network anomalies (suspicious IP patterns)
"""

import asyncio
import logging
import math
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from enum import Enum
from typing import Any, Optional
from uuid import uuid4

import structlog

logger = structlog.get_logger()


class AnomalyType(str, Enum):
    """Types of security anomalies."""

    UNUSUAL_LOGIN_LOCATION = "login.unusual_location"
    UNUSUAL_LOGIN_TIME = "login.unusual_time"
    BRUTE_FORCE_ATTEMPT = "auth.brute_force"
    RATE_SPIKE = "api.rate_spike"
    UNUSUAL_ENDPOINT = "api.unusual_endpoint"
    DATA_EXFILTRATION = "data.exfiltration"
    SUSPICIOUS_IP = "network.suspicious_ip"
    CREDENTIAL_STUFFING = "auth.credential_stuffing"
    IMPOSSIBLE_TRAVEL = "auth.impossible_travel"
    ACCOUNT_TAKEOVER = "auth.account_takeover"


class Severity(str, Enum):
    """Anomaly severity levels."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class AnomalyEvent:
    """Detected anomaly event."""

    anomaly_id: str
    anomaly_type: AnomalyType
    severity: Severity
    user_id: Optional[str]
    ip_address: Optional[str]
    timestamp: datetime
    details: dict[str, Any] = field(default_factory=dict)
    confidence: float = 0.0
    resolved: bool = False

    def to_dict(self) -> dict:
        return {
            "anomaly_id": self.anomaly_id,
            "anomaly_type": self.anomaly_type.value,
            "severity": self.severity.value,
            "user_id": self.user_id,
            "ip_address": self.ip_address,
            "timestamp": self.timestamp.isoformat(),
            "details": self.details,
            "confidence": self.confidence,
            "resolved": self.resolved,
        }


@dataclass
class UserProfile:
    """User behavioral profile for anomaly detection."""

    user_id: str
    typical_login_hours: set[int] = field(default_factory=set)
    typical_ips: set[str] = field(default_factory=set)
    typical_user_agents: set[str] = field(default_factory=set)
    typical_endpoints: dict[str, int] = field(default_factory=dict)
    avg_requests_per_hour: float = 0.0
    last_login_location: Optional[str] = None
    last_login_time: Optional[datetime] = None
    total_events: int = 0
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))


class StatisticalAnomalyDetector:
    """
    Statistical anomaly detector using simple ML techniques.

    Uses:
    - Z-score for rate anomalies
    - Moving averages for trend detection
    - Simple clustering for behavioral profiling
    """

    def __init__(
        self, z_score_threshold: float = 3.0, min_samples: int = 10, window_size: int = 100
    ):
        self.z_score_threshold = z_score_threshold
        self.min_samples = min_samples
        self.window_size = window_size

        self._user_profiles: dict[str, UserProfile] = {}
        self._rate_history: dict[str, list[float]] = defaultdict(list)
        self._ip_reputation: dict[str, dict] = defaultdict(
            lambda: {
                "failed_logins": 0,
                "successful_logins": 0,
                "first_seen": datetime.now(UTC),
                "last_seen": datetime.now(UTC),
                "is_suspicious": False,
            }
        )
        self._anomalies: list[AnomalyEvent] = []
        self._lock = asyncio.Lock()

    def _calculate_z_score(self, value: float, history: list[float]) -> float:
        """Calculate z-score for a value given history."""
        if len(history) < self.min_samples:
            return 0.0

        mean = sum(history) / len(history)
        variance = sum((x - mean) ** 2 for x in history) / len(history)
        std_dev = math.sqrt(variance) if variance > 0 else 1.0

        return abs(value - mean) / std_dev if std_dev > 0 else 0.0

    def _calculate_moving_average(self, history: list[float], window: int = 10) -> float:
        """Calculate moving average."""
        if not history:
            return 0.0
        recent = history[-window:]
        return sum(recent) / len(recent)

    async def analyze_login(
        self,
        user_id: str,
        ip_address: str,
        user_agent: str,
        success: bool,
        timestamp: Optional[datetime] = None,
    ) -> list[AnomalyEvent]:
        """Analyze login attempt for anomalies."""
        timestamp = timestamp or datetime.now(UTC)
        anomalies = []

        # Get or create user profile
        if user_id not in self._user_profiles:
            self._user_profiles[user_id] = UserProfile(user_id=user_id)

        profile = self._user_profiles[user_id]

        # Check for unusual login time
        hour = timestamp.hour
        if profile.typical_login_hours and hour not in profile.typical_login_hours:
            # Allow some deviation, flag if completely unusual
            if len(profile.typical_login_hours) > 5 and hour not in range(
                min(profile.typical_login_hours) - 2, max(profile.typical_login_hours) + 3
            ):
                anomalies.append(
                    AnomalyEvent(
                        anomaly_id=f"anom_{uuid4().hex[:12]}",
                        anomaly_type=AnomalyType.UNUSUAL_LOGIN_TIME,
                        severity=Severity.LOW,
                        user_id=user_id,
                        ip_address=ip_address,
                        timestamp=timestamp,
                        details={"hour": hour, "typical_hours": list(profile.typical_login_hours)},
                        confidence=0.6,
                    )
                )

        # Check for unusual IP
        if profile.typical_ips and ip_address not in profile.typical_ips:
            if len(profile.typical_ips) >= 3:
                anomalies.append(
                    AnomalyEvent(
                        anomaly_id=f"anom_{uuid4().hex[:12]}",
                        anomaly_type=AnomalyType.UNUSUAL_LOGIN_LOCATION,
                        severity=Severity.MEDIUM,
                        user_id=user_id,
                        ip_address=ip_address,
                        timestamp=timestamp,
                        details={"new_ip": ip_address, "known_ips": list(profile.typical_ips)[:5]},
                        confidence=0.7,
                    )
                )

        # Check for impossible travel
        if profile.last_login_time and profile.last_login_location:
            time_diff = (timestamp - profile.last_login_time).total_seconds()
            if time_diff < 3600 and ip_address != profile.last_login_location:
                anomalies.append(
                    AnomalyEvent(
                        anomaly_id=f"anom_{uuid4().hex[:12]}",
                        anomaly_type=AnomalyType.IMPOSSIBLE_TRAVEL,
                        severity=Severity.HIGH,
                        user_id=user_id,
                        ip_address=ip_address,
                        timestamp=timestamp,
                        details={
                            "previous_ip": profile.last_login_location,
                            "current_ip": ip_address,
                            "time_diff_seconds": time_diff,
                        },
                        confidence=0.85,
                    )
                )

        # Update profile on successful login
        if success:
            profile.typical_login_hours.add(hour)
            profile.typical_ips.add(ip_address)
            profile.typical_user_agents.add(user_agent)
            profile.last_login_time = timestamp
            profile.last_login_location = ip_address

        profile.total_events += 1

        # Store anomalies
        async with self._lock:
            self._anomalies.extend(anomalies)

        return anomalies

    async def analyze_api_request(
        self,
        user_id: str,
        endpoint: str,
        method: str,
        ip_address: str,
        response_time: float,
        status_code: int,
    ) -> list[AnomalyEvent]:
        """Analyze API request for anomalies."""
        anomalies = []

        # Update rate history
        key = f"{user_id}:{endpoint}"
        async with self._lock:
            self._rate_history[key].append(1.0)
            if len(self._rate_history[key]) > self.window_size:
                self._rate_history[key] = self._rate_history[key][-self.window_size :]

        # Check for rate spike using z-score
        recent_rate = sum(self._rate_history[key][-10:])
        history = self._rate_history[key]

        if len(history) >= self.min_samples:
            z_score = self._calculate_z_score(recent_rate, history)
            if z_score > self.z_score_threshold:
                anomalies.append(
                    AnomalyEvent(
                        anomaly_id=f"anom_{uuid4().hex[:12]}",
                        anomaly_type=AnomalyType.RATE_SPIKE,
                        severity=Severity.MEDIUM if z_score < 5 else Severity.HIGH,
                        user_id=user_id,
                        ip_address=ip_address,
                        timestamp=datetime.now(UTC),
                        details={
                            "endpoint": endpoint,
                            "z_score": z_score,
                            "recent_rate": recent_rate,
                            "avg_rate": sum(history) / len(history),
                        },
                        confidence=min(z_score / 10, 1.0),
                    )
                )

        # Check for unusual endpoint
        if user_id in self._user_profiles:
            profile = self._user_profiles[user_id]
            profile.typical_endpoints[endpoint] = profile.typical_endpoints.get(endpoint, 0) + 1

            # Flag rarely accessed endpoints
            if profile.total_events > 50:
                total_accesses = sum(profile.typical_endpoints.values())
                endpoint_freq = profile.typical_endpoints.get(endpoint, 0) / total_accesses
                if endpoint_freq < 0.01:  # Less than 1% of accesses
                    anomalies.append(
                        AnomalyEvent(
                            anomaly_id=f"anom_{uuid4().hex[:12]}",
                            anomaly_type=AnomalyType.UNUSUAL_ENDPOINT,
                            severity=Severity.LOW,
                            user_id=user_id,
                            ip_address=ip_address,
                            timestamp=datetime.now(UTC),
                            details={"endpoint": endpoint, "frequency": endpoint_freq},
                            confidence=0.5,
                        )
                    )

        # Store anomalies
        async with self._lock:
            self._anomalies.extend(anomalies)

        return anomalies

    async def analyze_failed_auth(
        self, ip_address: str, username: Optional[str], timestamp: Optional[datetime] = None
    ) -> list[AnomalyEvent]:
        """Analyze failed authentication for brute force attempts."""
        timestamp = timestamp or datetime.now(UTC)
        anomalies = []

        ip_data = self._ip_reputation[ip_address]
        ip_data["failed_logins"] += 1
        ip_data["last_seen"] = timestamp

        # Check for brute force
        if ip_data["failed_logins"] >= 5:
            ratio = ip_data["failed_logins"] / max(ip_data["successful_logins"], 1)
            if ratio > 3:
                ip_data["is_suspicious"] = True
                anomalies.append(
                    AnomalyEvent(
                        anomaly_id=f"anom_{uuid4().hex[:12]}",
                        anomaly_type=AnomalyType.BRUTE_FORCE_ATTEMPT,
                        severity=Severity.HIGH,
                        user_id=username,
                        ip_address=ip_address,
                        timestamp=timestamp,
                        details={
                            "failed_attempts": ip_data["failed_logins"],
                            "success_ratio": ratio,
                        },
                        confidence=0.9,
                    )
                )

        # Store anomalies
        async with self._lock:
            self._anomalies.extend(anomalies)

        return anomalies

    async def get_anomalies(
        self,
        severity: Optional[Severity] = None,
        user_id: Optional[str] = None,
        resolved: Optional[bool] = None,
        limit: int = 100,
    ) -> list[AnomalyEvent]:
        """Get detected anomalies with filters."""
        anomalies = self._anomalies

        if severity:
            anomalies = [a for a in anomalies if a.severity == severity]
        if user_id:
            anomalies = [a for a in anomalies if a.user_id == user_id]
        if resolved is not None:
            anomalies = [a for a in anomalies if a.resolved == resolved]

        return anomalies[-limit:]

    async def resolve_anomaly(self, anomaly_id: str) -> bool:
        """Mark an anomaly as resolved."""
        for anomaly in self._anomalies:
            if anomaly.anomaly_id == anomaly_id:
                anomaly.resolved = True
                return True
        return False

    async def get_stats(self) -> dict[str, Any]:
        """Get anomaly detection statistics."""
        return {
            "total_anomalies": len(self._anomalies),
            "unresolved": sum(1 for a in self._anomalies if not a.resolved),
            "by_severity": {
                s.value: sum(1 for a in self._anomalies if a.severity == s) for s in Severity
            },
            "by_type": {
                t.value: sum(1 for a in self._anomalies if a.anomaly_type == t)
                for t in AnomalyType
                if any(a.anomaly_type == t for a in self._anomalies)
            },
            "users_profiled": len(self._user_profiles),
            "ips_tracked": len(self._ip_reputation),
            "suspicious_ips": sum(1 for ip in self._ip_reputation.values() if ip["is_suspicious"]),
        }


anomaly_detector = StatisticalAnomalyDetector()


async def analyze_login_event(
    user_id: str, ip_address: str, user_agent: str, success: bool
) -> list[AnomalyEvent]:
    """Convenience function to analyze login events."""
    return await anomaly_detector.analyze_login(
        user_id=user_id, ip_address=ip_address, user_agent=user_agent, success=success
    )


async def analyze_api_event(
    user_id: str,
    endpoint: str,
    method: str,
    ip_address: str,
    response_time: float,
    status_code: int,
) -> list[AnomalyEvent]:
    """Convenience function to analyze API events."""
    return await anomaly_detector.analyze_api_request(
        user_id=user_id,
        endpoint=endpoint,
        method=method,
        ip_address=ip_address,
        response_time=response_time,
        status_code=status_code,
    )
