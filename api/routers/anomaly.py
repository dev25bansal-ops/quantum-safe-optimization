"""
Anomaly Detection Router.

API endpoints for anomaly detection and security monitoring.
"""

from datetime import UTC, datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from api.security.anomaly_detection import (
    AnomalyEvent,
    AnomalyType,
    Severity,
    anomaly_detector,
    analyze_login_event,
    analyze_api_event,
)

router = APIRouter(prefix="/anomaly", tags=["Anomaly Detection"])


def get_admin_user():
    """Stub for admin user dependency."""
    return {"user_id": "admin", "roles": ["admin"]}


@router.get("/stats")
async def get_anomaly_stats(admin: dict = Depends(get_admin_user)):
    """Get anomaly detection statistics."""
    return await anomaly_detector.get_stats()


@router.get("/anomalies")
async def list_anomalies(
    severity: Optional[Severity] = None,
    user_id: Optional[str] = None,
    resolved: Optional[bool] = None,
    limit: int = Query(default=100, le=1000),
    admin: dict = Depends(get_admin_user),
):
    """List detected anomalies with filters."""
    anomalies = await anomaly_detector.get_anomalies(
        severity=severity, user_id=user_id, resolved=resolved, limit=limit
    )
    return {"anomalies": [a.to_dict() for a in anomalies], "count": len(anomalies)}


@router.post("/anomalies/{anomaly_id}/resolve")
async def resolve_anomaly(anomaly_id: str, admin: dict = Depends(get_admin_user)):
    """Mark an anomaly as resolved."""
    resolved = await anomaly_detector.resolve_anomaly(anomaly_id)
    if not resolved:
        raise HTTPException(status_code=404, detail="Anomaly not found")
    return {"resolved": True, "anomaly_id": anomaly_id}


@router.get("/ip-reputation")
async def get_ip_reputation(
    ip_address: Optional[str] = None, admin: dict = Depends(get_admin_user)
):
    """Get IP reputation data."""
    if ip_address:
        if ip_address in anomaly_detector._ip_reputation:
            data = anomaly_detector._ip_reputation[ip_address]
            return {
                "ip_address": ip_address,
                "failed_logins": data["failed_logins"],
                "successful_logins": data["successful_logins"],
                "is_suspicious": data["is_suspicious"],
                "first_seen": data["first_seen"].isoformat(),
                "last_seen": data["last_seen"].isoformat(),
            }
        return {"ip_address": ip_address, "status": "unknown"}

    # Return summary of all tracked IPs
    return {
        "total_ips": len(anomaly_detector._ip_reputation),
        "suspicious_ips": [
            ip for ip, data in anomaly_detector._ip_reputation.items() if data["is_suspicious"]
        ][:100],
    }


@router.get("/user-profile/{user_id}")
async def get_user_profile(user_id: str, admin: dict = Depends(get_admin_user)):
    """Get user behavioral profile."""
    if user_id not in anomaly_detector._user_profiles:
        raise HTTPException(status_code=404, detail="User profile not found")

    profile = anomaly_detector._user_profiles[user_id]
    return {
        "user_id": profile.user_id,
        "typical_login_hours": list(profile.typical_login_hours),
        "known_ips": list(profile.typical_ips)[:10],
        "total_events": profile.total_events,
        "avg_requests_per_hour": profile.avg_requests_per_hour,
        "last_login": profile.last_login_time.isoformat() if profile.last_login_time else None,
    }


@router.post("/analyze/login")
async def analyze_login(
    user_id: str,
    ip_address: str,
    user_agent: str,
    success: bool,
    admin: dict = Depends(get_admin_user),
):
    """Manually trigger login analysis."""
    anomalies = await analyze_login_event(
        user_id=user_id, ip_address=ip_address, user_agent=user_agent, success=success
    )
    return {"anomalies_detected": len(anomalies), "anomalies": [a.to_dict() for a in anomalies]}


@router.get("/health")
async def anomaly_detection_health():
    """Health check for anomaly detection system."""
    stats = await anomaly_detector.get_stats()
    return {
        "status": "healthy",
        "users_profiled": stats["users_profiled"],
        "anomalies_detected": stats["total_anomalies"],
        "suspicious_ips": stats["suspicious_ips"],
    }
