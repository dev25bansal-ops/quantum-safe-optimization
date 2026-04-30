"""
Alert System - Router Endpoints.

Provides alert configuration, evaluation, and notification for monitoring.
"""

import asyncio
import logging
import os
import secrets
from collections import defaultdict
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from enum import Enum
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, WebSocket, WebSocketDisconnect
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

router = APIRouter()


class AlertSeverity(str, Enum):
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class AlertStatus(str, Enum):
    FIRING = "firing"
    RESOLVED = "resolved"
    SILENCED = "silenced"


class AlertCondition(str, Enum):
    GREATER_THAN = "gt"
    LESS_THAN = "lt"
    GREATER_THAN_OR_EQUAL = "gte"
    LESS_THAN_OR_EQUAL = "lte"
    EQUAL = "eq"
    NOT_EQUAL = "neq"


class AlertRuleCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    metric: str = Field(..., min_length=1)
    condition: AlertCondition
    threshold: float
    duration_seconds: int = Field(default=60, ge=0, le=3600)
    severity: AlertSeverity = AlertSeverity.WARNING
    description: str | None = None
    labels: dict[str, str] = {}
    enabled: bool = True


class AlertRuleUpdate(BaseModel):
    name: str | None = None
    metric: str | None = None
    condition: AlertCondition | None = None
    threshold: float | None = None
    duration_seconds: int | None = None
    severity: AlertSeverity | None = None
    description: str | None = None
    labels: dict[str, str] | None = None
    enabled: bool | None = None


class AlertRuleResponse(BaseModel):
    id: str
    name: str
    metric: str
    condition: str
    threshold: float
    duration_seconds: int
    severity: str
    description: str | None
    labels: dict[str, str]
    enabled: bool
    created_at: str
    updated_at: str


class AlertInstanceResponse(BaseModel):
    id: str
    rule_id: str
    rule_name: str | None
    status: str
    severity: str
    metric: str
    value: float
    threshold: float
    started_at: str
    resolved_at: str | None
    acknowledged: bool


class AlertListResponse(BaseModel):
    alerts: list[AlertInstanceResponse]
    total: int


_alert_rules: dict[str, dict[str, Any]] = {}
_active_alerts: dict[str, dict[str, Any]] = {}
_alert_history: list[dict[str, Any]] = []
_metric_values: dict[str, list[tuple[float, float]]] = defaultdict(list)
_websocket_clients: set[WebSocket] = set()


def get_user_id() -> str:
    return "user_default"


def _evaluate_condition(value: float, condition: AlertCondition, threshold: float) -> bool:
    ops = {
        AlertCondition.GREATER_THAN: lambda v, t: v > t,
        AlertCondition.LESS_THAN: lambda v, t: v < t,
        AlertCondition.GREATER_THAN_OR_EQUAL: lambda v, t: v >= t,
        AlertCondition.LESS_THAN_OR_EQUAL: lambda v, t: v <= t,
        AlertCondition.EQUAL: lambda v, t: v == t,
        AlertCondition.NOT_EQUAL: lambda v, t: v != t,
    }
    return ops.get(condition, lambda v, t: False)(value, threshold)


async def _broadcast_alert(alert_data: dict[str, Any]) -> None:
    dead_clients = set()
    for ws in _websocket_clients:
        try:
            await ws.send_json(alert_data)
        except Exception:
            dead_clients.add(ws)
    _websocket_clients.difference_update(dead_clients)


async def evaluate_alert(rule_id: str) -> None:
    rule = _alert_rules.get(rule_id)
    if not rule or not rule["enabled"]:
        return

    metric = rule["metric"]
    values = _metric_values.get(metric, [])

    if not values:
        return

    now = time.time()
    cutoff = now - rule["duration_seconds"]
    recent_values = [(t, v) for t, v in values if t > cutoff]

    if not recent_values:
        return

    avg_value = sum(v for _, v in recent_values) / len(recent_values)
    condition = AlertCondition(rule["condition"])
    is_firing = _evaluate_condition(avg_value, condition, rule["threshold"])

    existing_alert_id = None
    for aid, alert in _active_alerts.items():
        if alert["rule_id"] == rule_id and alert["status"] == AlertStatus.FIRING.value:
            existing_alert_id = aid
            break

    if is_firing and not existing_alert_id:
        alert_id = f"alert_{secrets.token_hex(8)}"
        alert = {
            "id": alert_id,
            "rule_id": rule_id,
            "rule_name": rule["name"],
            "status": AlertStatus.FIRING.value,
            "severity": rule["severity"],
            "metric": metric,
            "value": avg_value,
            "threshold": rule["threshold"],
            "started_at": datetime.now(UTC).isoformat(),
            "resolved_at": None,
            "acknowledged": False,
        }
        _active_alerts[alert_id] = alert
        _alert_history.append(alert.copy())
        await _broadcast_alert({"type": "alert_firing", "alert": alert})
        logger.warning("alert_fired", alert_id=alert_id, rule=rule["name"], value=avg_value)

    elif not is_firing and existing_alert_id:
        alert = _active_alerts[existing_alert_id]
        alert["status"] = AlertStatus.RESOLVED.value
        alert["resolved_at"] = datetime.now(UTC).isoformat()
        alert["value"] = avg_value
        _alert_history.append(alert.copy())
        del _active_alerts[existing_alert_id]
        await _broadcast_alert({"type": "alert_resolved", "alert": alert})
        logger.info("alert_resolved", alert_id=existing_alert_id, rule=rule["name"])


import time as time_module


async def record_metric(name: str, value: float) -> None:
    _metric_values[name].append((time_module.time(), value))
    _metric_values[name] = _metric_values[name][-1000:]

    for rule_id, rule in _alert_rules.items():
        if rule["metric"] == name:
            await evaluate_alert(rule_id)


@router.post("/rules", response_model=AlertRuleResponse, status_code=201)
async def create_alert_rule(
    request: AlertRuleCreate,
    user_id: str = Depends(get_user_id),
):
    rule_id = f"rule_{secrets.token_hex(8)}"
    now = datetime.now(UTC).isoformat()

    _alert_rules[rule_id] = {
        "id": rule_id,
        "name": request.name,
        "metric": request.metric,
        "condition": request.condition.value,
        "threshold": request.threshold,
        "duration_seconds": request.duration_seconds,
        "severity": request.severity.value,
        "description": request.description,
        "labels": request.labels,
        "enabled": request.enabled,
        "created_at": now,
        "updated_at": now,
        "user_id": user_id,
    }

    rule = _alert_rules[rule_id]
    return AlertRuleResponse(**rule)


@router.get("/rules")
async def list_alert_rules(
    user_id: str = Depends(get_user_id),
    enabled: bool | None = None,
    severity: AlertSeverity | None = None,
    limit: int = Query(default=50, le=200),
):
    rules = list(_alert_rules.values())

    if enabled is not None:
        rules = [r for r in rules if r["enabled"] == enabled]
    if severity:
        rules = [r for r in rules if r["severity"] == severity.value]

    return {"rules": rules[:limit], "total": len(rules)}


@router.get("/rules/{rule_id}", response_model=AlertRuleResponse)
async def get_alert_rule(
    rule_id: str,
    user_id: str = Depends(get_user_id),
):
    if rule_id not in _alert_rules:
        raise HTTPException(status_code=404, detail="Alert rule not found")
    return AlertRuleResponse(**_alert_rules[rule_id])


@router.patch("/rules/{rule_id}", response_model=AlertRuleResponse)
async def update_alert_rule(
    rule_id: str,
    request: AlertRuleUpdate,
    user_id: str = Depends(get_user_id),
):
    if rule_id not in _alert_rules:
        raise HTTPException(status_code=404, detail="Alert rule not found")

    rule = _alert_rules[rule_id]
    update_data = request.model_dump(exclude_unset=True)

    for key, value in update_data.items():
        if key == "condition" and value:
            rule[key] = value.value
        elif key == "severity" and value:
            rule[key] = value.value
        else:
            rule[key] = value

    rule["updated_at"] = datetime.now(UTC).isoformat()
    return AlertRuleResponse(**rule)


@router.delete("/rules/{rule_id}")
async def delete_alert_rule(
    rule_id: str,
    user_id: str = Depends(get_user_id),
):
    if rule_id not in _alert_rules:
        raise HTTPException(status_code=404, detail="Alert rule not found")

    del _alert_rules[rule_id]
    return {"status": "deleted", "rule_id": rule_id}


@router.get("/active")
async def list_active_alerts(
    user_id: str = Depends(get_user_id),
    severity: AlertSeverity | None = None,
    limit: int = Query(default=100, le=500),
):
    alerts = list(_active_alerts.values())

    if severity:
        alerts = [a for a in alerts if a["severity"] == severity.value]

    return AlertListResponse(
        alerts=[
            AlertInstanceResponse(
                id=a["id"],
                rule_id=a["rule_id"],
                rule_name=a.get("rule_name"),
                status=a["status"],
                severity=a["severity"],
                metric=a["metric"],
                value=a["value"],
                threshold=a["threshold"],
                started_at=a["started_at"],
                resolved_at=a.get("resolved_at"),
                acknowledged=a.get("acknowledged", False),
            )
            for a in alerts[:limit]
        ],
        total=len(alerts),
    )


@router.post("/alerts/{alert_id}/acknowledge")
async def acknowledge_alert(
    alert_id: str,
    user_id: str = Depends(get_user_id),
):
    if alert_id not in _active_alerts:
        raise HTTPException(status_code=404, detail="Alert not found")

    _active_alerts[alert_id]["acknowledged"] = True
    _active_alerts[alert_id]["acknowledged_at"] = datetime.now(UTC).isoformat()
    _active_alerts[alert_id]["acknowledged_by"] = user_id

    return {"status": "acknowledged", "alert_id": alert_id}


@router.post("/alerts/{alert_id}/silence")
async def silence_alert(
    alert_id: str,
    duration_minutes: int = Query(default=60, ge=1, le=1440),
    user_id: str = Depends(get_user_id),
):
    if alert_id not in _active_alerts:
        raise HTTPException(status_code=404, detail="Alert not found")

    _active_alerts[alert_id]["status"] = AlertStatus.SILENCED.value
    _active_alerts[alert_id]["silenced_until"] = (
        datetime.now(UTC) + timedelta(minutes=duration_minutes)
    ).isoformat()

    return {
        "status": "silenced",
        "alert_id": alert_id,
        "until": _active_alerts[alert_id]["silenced_until"],
    }


@router.get("/history")
async def get_alert_history(
    user_id: str = Depends(get_user_id),
    hours: int = Query(default=24, ge=1, le=168),
    limit: int = Query(default=100, le=500),
):
    cutoff = datetime.now(UTC) - timedelta(hours=hours)
    recent = [a for a in _alert_history if datetime.fromisoformat(a["started_at"]) > cutoff]
    return {"alerts": recent[-limit:], "total": len(recent)}


@router.post("/metrics/{metric_name}")
async def submit_metric(
    metric_name: str,
    value: float,
    user_id: str = Depends(get_user_id),
):
    await record_metric(metric_name, value)
    return {"status": "recorded", "metric": metric_name, "value": value}


@router.websocket("/ws")
async def alerts_websocket(websocket: WebSocket):
    await websocket.accept()
    _websocket_clients.add(websocket)

    try:
        await websocket.send_json({"type": "connected", "timestamp": datetime.now(UTC).isoformat()})

        while True:
            try:
                data = await asyncio.wait_for(websocket.receive_json(), timeout=30.0)
                if data.get("type") == "ping":
                    await websocket.send_json(
                        {"type": "pong", "timestamp": datetime.now(UTC).isoformat()}
                    )
            except asyncio.TimeoutError:
                await websocket.send_json(
                    {"type": "ping", "timestamp": datetime.now(UTC).isoformat()}
                )

    except WebSocketDisconnect:
        pass
    except Exception as e:
        logger.error("alerts_websocket_error", error=str(e))
    finally:
        _websocket_clients.discard(websocket)


@router.get("/health")
async def alerts_health():
    return {
        "status": "healthy",
        "active_rules": len(_alert_rules),
        "active_alerts": len(_active_alerts),
        "websocket_clients": len(_websocket_clients),
        "timestamp": datetime.now(UTC).isoformat(),
    }
