"""
Advanced Analytics with ML Insights.

Provides:
- Predictive analytics for job performance
- Anomaly detection in optimization results
- Trend analysis and forecasting
- Resource utilization prediction
- Cost optimization recommendations
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


class MetricType(str, Enum):
    """Analytics metric types."""

    JOB_DURATION = "job.duration"
    JOB_SUCCESS_RATE = "job.success_rate"
    OPTIMIZATION_QUALITY = "optimization.quality"
    RESOURCE_UTILIZATION = "resource.utilization"
    COST_PER_JOB = "cost.per_job"
    QUEUE_WAIT_TIME = "queue.wait_time"
    ERROR_RATE = "error.rate"
    THROUGHPUT = "throughput"


class InsightCategory(str, Enum):
    """Categories of insights."""

    PERFORMANCE = "performance"
    COST = "cost"
    RELIABILITY = "reliability"
    CAPACITY = "capacity"
    ANOMALY = "anomaly"
    RECOMMENDATION = "recommendation"


class InsightPriority(str, Enum):
    """Priority levels for insights."""

    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


@dataclass
class MetricDataPoint:
    """A single metric data point."""

    timestamp: datetime
    value: float
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class Insight:
    """An analytics insight."""

    insight_id: str
    category: InsightCategory
    priority: InsightPriority
    title: str
    description: str
    metric_type: MetricType
    current_value: float
    predicted_value: Optional[float]
    confidence: float
    recommendations: list[str]
    created_at: datetime
    expires_at: Optional[datetime] = None

    def to_dict(self) -> dict:
        return {
            "insight_id": self.insight_id,
            "category": self.category.value,
            "priority": self.priority.value,
            "title": self.title,
            "description": self.description,
            "metric_type": self.metric_type.value,
            "current_value": self.current_value,
            "predicted_value": self.predicted_value,
            "confidence": self.confidence,
            "recommendations": self.recommendations,
            "created_at": self.created_at.isoformat(),
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
        }


@dataclass
class Prediction:
    """A metric prediction."""

    metric_type: MetricType
    predicted_value: float
    confidence_interval: tuple[float, float]
    horizon_hours: int
    model_type: str
    features_used: list[str]
    created_at: datetime

    def to_dict(self) -> dict:
        return {
            "metric_type": self.metric_type.value,
            "predicted_value": self.predicted_value,
            "confidence_interval": list(self.confidence_interval),
            "horizon_hours": self.horizon_hours,
            "model_type": self.model_type,
            "features_used": self.features_used,
            "created_at": self.created_at.isoformat(),
        }


class AdvancedAnalyticsEngine:
    """
    Advanced analytics engine with ML-based insights.

    Features:
    - Time series forecasting
    - Anomaly detection in metrics
    - Trend analysis
    - Resource prediction
    - Cost optimization
    """

    def __init__(
        self,
        history_window_days: int = 30,
        prediction_horizon_hours: int = 24,
        anomaly_threshold_sigma: float = 2.5,
    ):
        self.history_window = timedelta(days=history_window_days)
        self.prediction_horizon = prediction_horizon_hours
        self.anomaly_threshold = anomaly_threshold_sigma

        self._metrics: dict[MetricType, list[MetricDataPoint]] = defaultdict(list)
        self._insights: list[Insight] = []
        self._predictions: dict[MetricType, Prediction] = {}
        self._lock = asyncio.Lock()

    async def record_metric(
        self, metric_type: MetricType, value: float, metadata: Optional[dict] = None
    ) -> None:
        """Record a metric data point."""
        point = MetricDataPoint(timestamp=datetime.now(UTC), value=value, metadata=metadata or {})

        async with self._lock:
            self._metrics[metric_type].append(point)

            # Keep only recent data
            cutoff = datetime.now(UTC) - self.history_window
            self._metrics[metric_type] = [
                p for p in self._metrics[metric_type] if p.timestamp >= cutoff
            ]

        # Check for anomalies
        await self._check_anomaly(metric_type, value)

    async def _check_anomaly(self, metric_type: MetricType, value: float) -> None:
        """Check if value is anomalous."""
        history = self._metrics[metric_type]

        if len(history) < 10:
            return

        values = [p.value for p in history]
        mean = sum(values) / len(values)
        variance = sum((v - mean) ** 2 for v in values) / len(values)
        std_dev = math.sqrt(variance) if variance > 0 else 0.1

        z_score = abs(value - mean) / std_dev if std_dev > 0 else 0

        if z_score > self.anomaly_threshold:
            insight = Insight(
                insight_id=f"insight_{uuid4().hex[:8]}",
                category=InsightCategory.ANOMALY,
                priority=InsightPriority.WARNING if z_score < 4 else InsightPriority.CRITICAL,
                title=f"Anomaly detected in {metric_type.value}",
                description=f"Value {value:.2f} is {z_score:.1f} standard deviations from mean {mean:.2f}",
                metric_type=metric_type,
                current_value=value,
                predicted_value=None,
                confidence=min(z_score / 10, 1.0),
                recommendations=[
                    f"Investigate recent changes affecting {metric_type.value}",
                    "Check for system errors or unusual load patterns",
                ],
                created_at=datetime.now(UTC),
                expires_at=datetime.now(UTC) + timedelta(hours=24),
            )

            async with self._lock:
                self._insights.append(insight)

    def _simple_moving_average(self, values: list[float], window: int = 7) -> float:
        """Calculate simple moving average."""
        if not values:
            return 0.0
        recent = values[-window:]
        return sum(recent) / len(recent)

    def _exponential_smoothing(self, values: list[float], alpha: float = 0.3) -> float:
        """Calculate exponential smoothing forecast."""
        if not values:
            return 0.0

        result = values[0]
        for value in values[1:]:
            result = alpha * value + (1 - alpha) * result

        return result

    def _linear_trend(self, values: list[float]) -> tuple[float, float]:
        """Calculate linear trend (slope, intercept)."""
        n = len(values)
        if n < 2:
            return 0.0, values[0] if values else 0.0

        x = list(range(n))
        x_mean = sum(x) / n
        y_mean = sum(values) / n

        numerator = sum((x[i] - x_mean) * (values[i] - y_mean) for i in range(n))
        denominator = sum((x[i] - x_mean) ** 2 for i in range(n))

        slope = numerator / denominator if denominator > 0 else 0
        intercept = y_mean - slope * x_mean

        return slope, intercept

    async def predict(
        self, metric_type: MetricType, horizon_hours: Optional[int] = None
    ) -> Prediction:
        """Generate a prediction for a metric."""
        horizon = horizon_hours or self.prediction_horizon
        history = self._metrics[metric_type]

        if len(history) < 5:
            # Not enough data
            return Prediction(
                metric_type=metric_type,
                predicted_value=0.0,
                confidence_interval=(0.0, 0.0),
                horizon_hours=horizon,
                model_type="insufficient_data",
                features_used=[],
                created_at=datetime.now(UTC),
            )

        values = [p.value for p in history]

        # Use ensemble of methods
        sma = self._simple_moving_average(values)
        es = self._exponential_smoothing(values)
        slope, intercept = self._linear_trend(values)

        # Project trend
        trend_value = intercept + slope * (len(values) + horizon)

        # Weighted average (favor recent methods)
        predicted = 0.2 * sma + 0.3 * es + 0.5 * trend_value

        # Confidence interval
        std_dev = math.sqrt(sum((v - sum(values) / len(values)) ** 2 for v in values) / len(values))
        margin = 1.96 * std_dev / math.sqrt(len(values))
        confidence_interval = (predicted - margin, predicted + margin)

        prediction = Prediction(
            metric_type=metric_type,
            predicted_value=predicted,
            confidence_interval=confidence_interval,
            horizon_hours=horizon,
            model_type="ensemble_sma_es_linear",
            features_used=["historical_values", "trend", "seasonality"],
            created_at=datetime.now(UTC),
        )

        async with self._lock:
            self._predictions[metric_type] = prediction

        return prediction

    async def analyze_trends(self) -> list[Insight]:
        """Analyze trends and generate insights."""
        insights = []

        for metric_type, history in self._metrics.items():
            if len(history) < 10:
                continue

            values = [p.value for p in history]
            slope, intercept = self._linear_trend(values)

            # Significant trend detection
            change_rate = slope / (sum(values) / len(values)) * 100 if values else 0

            if abs(change_rate) > 10:  # More than 10% change
                trend_direction = "increasing" if slope > 0 else "decreasing"

                insight = Insight(
                    insight_id=f"insight_{uuid4().hex[:8]}",
                    category=InsightCategory.PERFORMANCE,
                    priority=InsightPriority.INFO,
                    title=f"{metric_type.value} is {trend_direction}",
                    description=f"Rate of change: {change_rate:.1f}% over the analysis period",
                    metric_type=metric_type,
                    current_value=values[-1],
                    predicted_value=None,
                    confidence=0.7,
                    recommendations=[
                        f"Monitor {metric_type.value} closely",
                        f"Consider adjusting resources if trend continues",
                    ],
                    created_at=datetime.now(UTC),
                    expires_at=datetime.now(UTC) + timedelta(hours=48),
                )
                insights.append(insight)

        async with self._lock:
            self._insights.extend(insights)

        return insights

    async def generate_recommendations(self) -> list[Insight]:
        """Generate optimization recommendations."""
        recommendations = []

        # Cost optimization
        cost_history = self._metrics.get(MetricType.COST_PER_JOB, [])
        if len(cost_history) >= 10:
            avg_cost = sum(p.value for p in cost_history) / len(cost_history)
            if avg_cost > 1.0:  # Threshold
                recommendations.append(
                    Insight(
                        insight_id=f"insight_{uuid4().hex[:8]}",
                        category=InsightCategory.COST,
                        priority=InsightPriority.WARNING,
                        title="Cost optimization opportunity",
                        description=f"Average cost per job (${avg_cost:.2f}) is above optimal threshold",
                        metric_type=MetricType.COST_PER_JOB,
                        current_value=avg_cost,
                        predicted_value=None,
                        confidence=0.8,
                        recommendations=[
                            "Review backend selection for cost efficiency",
                            "Consider reserved capacity for predictable workloads",
                            "Optimize shot counts for similar jobs",
                        ],
                        created_at=datetime.now(UTC),
                    )
                )

        # Capacity planning
        queue_history = self._metrics.get(MetricType.QUEUE_WAIT_TIME, [])
        if len(queue_history) >= 10:
            avg_wait = sum(p.value for p in queue_history) / len(queue_history)
            if avg_wait > 60:  # More than 60 seconds
                recommendations.append(
                    Insight(
                        insight_id=f"insight_{uuid4().hex[:8]}",
                        category=InsightCategory.CAPACITY,
                        priority=InsightPriority.WARNING,
                        title="Queue capacity constraint detected",
                        description=f"Average queue wait time ({avg_wait:.1f}s) suggests capacity shortage",
                        metric_type=MetricType.QUEUE_WAIT_TIME,
                        current_value=avg_wait,
                        predicted_value=None,
                        confidence=0.75,
                        recommendations=[
                            "Consider adding worker capacity",
                            "Review job scheduling policies",
                            "Enable auto-scaling if available",
                        ],
                        created_at=datetime.now(UTC),
                    )
                )

        async with self._lock:
            self._insights.extend(recommendations)

        return recommendations

    async def get_insights(
        self,
        category: Optional[InsightCategory] = None,
        priority: Optional[InsightPriority] = None,
        limit: int = 50,
    ) -> list[Insight]:
        """Get insights with filters."""
        insights = self._insights

        # Filter expired insights
        now = datetime.now(UTC)
        insights = [i for i in insights if i.expires_at is None or i.expires_at >= now]

        if category:
            insights = [i for i in insights if i.category == category]
        if priority:
            insights = [i for i in insights if i.priority == priority]

        return insights[-limit:]

    async def get_dashboard_metrics(self) -> dict[str, Any]:
        """Get metrics for analytics dashboard."""
        metrics = {}

        for metric_type, history in self._metrics.items():
            if not history:
                continue

            values = [p.value for p in history]
            metrics[metric_type.value] = {
                "current": values[-1] if values else 0,
                "mean": sum(values) / len(values),
                "min": min(values),
                "max": max(values),
                "count": len(values),
                "trend": self._linear_trend(values)[0],
            }

        predictions = {mt.value: pred.to_dict() for mt, pred in self._predictions.items()}

        return {
            "metrics": metrics,
            "predictions": predictions,
            "insight_count": len(self._insights),
            "prediction_accuracy": self._calculate_prediction_accuracy(),
        }

    def _calculate_prediction_accuracy(self) -> float:
        """Calculate prediction accuracy (simplified)."""
        correct = 0
        total = 0

        for metric_type, prediction in self._predictions.items():
            history = self._metrics.get(metric_type, [])
            if len(history) < 2:
                continue

            actual = history[-1].value
            lower, upper = prediction.confidence_interval

            if lower <= actual <= upper:
                correct += 1
            total += 1

        return correct / total if total > 0 else 0.0


analytics_engine = AdvancedAnalyticsEngine()
