"""
Performance Profiler Module.

Provides comprehensive performance analysis and profiling tools for
quantum optimization jobs, including execution time analysis, resource
utilization tracking, bottleneck identification, and optimization recommendations.
"""

import logging
import time
import asyncio
from typing import Any, Dict, List, Optional, Tuple, Callable
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime, timedelta
from collections import defaultdict
import json
import statistics

logger = logging.getLogger(__name__)


class MetricType(Enum):
    """Types of performance metrics."""
    EXECUTION_TIME = "execution_time"
    MEMORY_USAGE = "memory_usage"
    CPU_USAGE = "cpu_usage"
    QUANTUM_OPERATIONS = "quantum_operations"
    CIRCUIT_DEPTH = "circuit_depth"
    GATE_COUNT = "gate_count"
    SHOT_COUNT = "shot_count"
    CONVERGENCE_RATE = "convergence_rate"
    ERROR_RATE = "error_rate"


class PerformanceLevel(Enum):
    """Performance level classifications."""
    EXCELLENT = "excellent"
    GOOD = "good"
    FAIR = "fair"
    POOR = "poor"


@dataclass
class PerformanceMetric:
    """Represents a single performance metric."""
    
    metric_type: MetricType
    value: float
    unit: str
    timestamp: datetime = field(default_factory=datetime.now)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "metric_type": self.metric_type.value,
            "value": self.value,
            "unit": self.unit,
            "timestamp": self.timestamp.isoformat(),
            "metadata": self.metadata,
        }


@dataclass
class PerformanceProfile:
    """Performance profile for a job or operation."""
    
    profile_id: str
    name: str
    created_at: datetime = field(default_factory=datetime.now)
    metrics: List[PerformanceMetric] = field(default_factory=list)
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    
    @property
    def duration(self) -> Optional[timedelta]:
        """Get profile duration."""
        if self.start_time and self.end_time:
            return self.end_time - self.start_time
        return None
    
    @property
    def is_complete(self) -> bool:
        """Check if profile is complete."""
        return self.start_time is not None and self.end_time is not None
    
    def add_metric(self, metric: PerformanceMetric) -> None:
        """Add a metric to the profile."""
        self.metrics.append(metric)
    
    def get_metric(self, metric_type: MetricType) -> Optional[PerformanceMetric]:
        """Get a specific metric by type."""
        for metric in self.metrics:
            if metric.metric_type == metric_type:
                return metric
        return None
    
    def get_metrics_by_type(self, metric_type: MetricType) -> List[PerformanceMetric]:
        """Get all metrics of a specific type."""
        return [m for m in self.metrics if m.metric_type == metric_type]
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "profile_id": self.profile_id,
            "name": self.name,
            "created_at": self.created_at.isoformat(),
            "start_time": self.start_time.isoformat() if self.start_time else None,
            "end_time": self.end_time.isoformat() if self.end_time else None,
            "duration": str(self.duration) if self.duration else None,
            "metrics": [m.to_dict() for m in self.metrics],
            "metric_count": len(self.metrics),
        }


@dataclass
class PerformanceBenchmark:
    """Performance benchmark for comparison."""
    
    benchmark_id: str
    name: str
    baseline_metrics: Dict[MetricType, float] = field(default_factory=dict)
    target_metrics: Dict[MetricType, float] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.now)
    
    def compare(self, profile: PerformanceProfile) -> Dict[str, Any]:
        """Compare profile against benchmark."""
        comparison = {
            "benchmark_id": self.benchmark_id,
            "profile_id": profile.profile_id,
            "metrics": {},
            "overall_score": 0.0,
        }
        
        total_score = 0.0
        metric_count = 0
        
        for metric_type, target_value in self.target_metrics.items():
            profile_metric = profile.get_metric(metric_type)
            
            if profile_metric is None:
                continue
            
            baseline_value = self.baseline_metrics.get(metric_type, target_value)
            
            # Calculate score (0-1, where 1 is meeting or exceeding target)
            if metric_type in [MetricType.EXECUTION_TIME, MetricType.MEMORY_USAGE]:
                # Lower is better
                score = min(1.0, baseline_value / profile_metric.value)
            else:
                # Higher is better
                score = min(1.0, profile_metric.value / target_value)
            
            comparison["metrics"][metric_type.value] = {
                "baseline": baseline_value,
                "target": target_value,
                "actual": profile_metric.value,
                "score": score,
                "unit": profile_metric.unit,
            }
            
            total_score += score
            metric_count += 1
        
        if metric_count > 0:
            comparison["overall_score"] = total_score / metric_count
        
        return comparison


class PerformanceProfiler:
    """Main performance profiler for quantum operations."""
    
    def __init__(self):
        self._profiles: Dict[str, PerformanceProfile] = {}
        self._benchmarks: Dict[str, PerformanceBenchmark] = {}
        self._active_profile: Optional[PerformanceProfile] = None
        self._statistics: Dict[str, List[float]] = defaultdict(list)
    
    def create_profile(
        self,
        profile_id: str,
        name: str
    ) -> PerformanceProfile:
        """Create a new performance profile."""
        profile = PerformanceProfile(
            profile_id=profile_id,
            name=name
        )
        self._profiles[profile_id] = profile
        return profile
    
    def get_profile(self, profile_id: str) -> Optional[PerformanceProfile]:
        """Get a performance profile by ID."""
        return self._profiles.get(profile_id)
    
    def delete_profile(self, profile_id: str) -> bool:
        """Delete a performance profile."""
        if profile_id in self._profiles:
            del self._profiles[profile_id]
            return True
        return False
    
    def list_profiles(self) -> List[PerformanceProfile]:
        """List all performance profiles."""
        return list(self._profiles.values())
    
    def start_profiling(self, profile_id: str) -> PerformanceProfile:
        """Start profiling for a profile."""
        profile = self.get_profile(profile_id)
        if profile is None:
            raise ValueError(f"Profile {profile_id} not found")
        
        profile.start_time = datetime.now()
        self._active_profile = profile
        
        logger.info(f"Started profiling: {profile.name} ({profile_id})")
        
        return profile
    
    def stop_profiling(self, profile_id: str) -> PerformanceProfile:
        """Stop profiling for a profile."""
        profile = self.get_profile(profile_id)
        if profile is None:
            raise ValueError(f"Profile {profile_id} not found")
        
        profile.end_time = datetime.now()
        
        if self._active_profile == profile:
            self._active_profile = None
        
        logger.info(f"Stopped profiling: {profile.name} ({profile_id})")
        
        return profile
    
    def record_metric(
        self,
        profile_id: str,
        metric_type: MetricType,
        value: float,
        unit: str = "",
        metadata: Optional[Dict[str, Any]] = None
    ) -> None:
        """Record a performance metric."""
        profile = self.get_profile(profile_id)
        if profile is None:
            raise ValueError(f"Profile {profile_id} not found")
        
        metric = PerformanceMetric(
            metric_type=metric_type,
            value=value,
            unit=unit,
            metadata=metadata or {}
        )
        
        profile.add_metric(metric)
        
        # Track statistics
        self._statistics[metric_type.value].append(value)
        
        logger.debug(
            f"Recorded metric {metric_type.value} = {value} {unit} "
            f"for profile {profile_id}"
        )
    
    def get_statistics(self, metric_type: MetricType) -> Dict[str, float]:
        """Get statistical summary for a metric type."""
        values = self._statistics.get(metric_type.value, [])
        
        if not values:
            return {}
        
        return {
            "count": len(values),
            "min": min(values),
            "max": max(values),
            "mean": statistics.mean(values),
            "median": statistics.median(values),
            "stdev": statistics.stdev(values) if len(values) > 1 else 0.0,
        }
    
    def create_benchmark(
        self,
        benchmark_id: str,
        name: str,
        baseline_metrics: Dict[MetricType, float],
        target_metrics: Dict[MetricType, float]
    ) -> PerformanceBenchmark:
        """Create a performance benchmark."""
        benchmark = PerformanceBenchmark(
            benchmark_id=benchmark_id,
            name=name,
            baseline_metrics=baseline_metrics,
            target_metrics=target_metrics
        )
        self._benchmarks[benchmark_id] = benchmark
        return benchmark
    
    def get_benchmark(self, benchmark_id: str) -> Optional[PerformanceBenchmark]:
        """Get a benchmark by ID."""
        return self._benchmarks.get(benchmark_id)
    
    def compare_to_benchmark(
        self,
        profile_id: str,
        benchmark_id: str
    ) -> Optional[Dict[str, Any]]:
        """Compare a profile against a benchmark."""
        profile = self.get_profile(profile_id)
        benchmark = self.get_benchmark(benchmark_id)
        
        if profile is None or benchmark is None:
            return None
        
        return benchmark.compare(profile)
    
    def analyze_performance(self, profile_id: str) -> Dict[str, Any]:
        """Analyze performance profile and provide insights."""
        profile = self.get_profile(profile_id)
        if profile is None:
            raise ValueError(f"Profile {profile_id} not found")
        
        analysis = {
            "profile_id": profile_id,
            "name": profile.name,
            "duration": str(profile.duration) if profile.duration else None,
            "metric_summary": {},
            "bottlenecks": [],
            "recommendations": [],
            "performance_level": PerformanceLevel.GOOD.value,
        }
        
        # Analyze each metric
        for metric in profile.metrics:
            metric_analysis = self._analyze_metric(metric)
            analysis["metric_summary"][metric.metric_type.value] = metric_analysis
            
            # Identify bottlenecks
            if metric_analysis.get("is_bottleneck"):
                analysis["bottlenecks"].append({
                    "metric_type": metric.metric_type.value,
                    "value": metric.value,
                    "threshold": metric_analysis.get("threshold"),
                    "severity": metric_analysis.get("severity"),
                })
        
        # Generate recommendations
        analysis["recommendations"] = self._generate_recommendations(profile)
        
        # Determine overall performance level
        analysis["performance_level"] = self._determine_performance_level(profile)
        
        return analysis
    
    def _analyze_metric(self, metric: PerformanceMetric) -> Dict[str, Any]:
        """Analyze a single metric."""
        analysis = {
            "value": metric.value,
            "unit": metric.unit,
            "is_bottleneck": False,
            "severity": "low",
        }
        
        # Get statistics for this metric type
        stats = self.get_statistics(metric.metric_type)
        
        if stats:
            # Compare to historical data
            mean = stats["mean"]
            stdev = stats["stdev"]
            
            # Check if value is significantly worse than average
            if metric.metric_type in [MetricType.EXECUTION_TIME, MetricType.MEMORY_USAGE]:
                # Lower is better
                if metric.value > mean + 2 * stdev:
                    analysis["is_bottleneck"] = True
                    analysis["severity"] = "high"
                    analysis["threshold"] = mean + 2 * stdev
                elif metric.value > mean + stdev:
                    analysis["is_bottleneck"] = True
                    analysis["severity"] = "medium"
                    analysis["threshold"] = mean + stdev
            else:
                # Higher is better
                if metric.value < mean - 2 * stdev:
                    analysis["is_bottleneck"] = True
                    analysis["severity"] = "high"
                    analysis["threshold"] = mean - 2 * stdev
                elif metric.value < mean - stdev:
                    analysis["is_bottleneck"] = True
                    analysis["severity"] = "medium"
                    analysis["threshold"] = mean - stdev
        
        return analysis
    
    def _generate_recommendations(self, profile: PerformanceProfile) -> List[str]:
        """Generate performance optimization recommendations."""
        recommendations = []
        
        # Check execution time
        exec_time = profile.get_metric(MetricType.EXECUTION_TIME)
        if exec_time and exec_time.value > 60.0:
            recommendations.append(
                "Consider optimizing algorithm parameters or using "
                "a more efficient backend to reduce execution time."
            )
        
        # Check memory usage
        memory = profile.get_metric(MetricType.MEMORY_USAGE)
        if memory and memory.value > 1024:  # > 1GB
            recommendations.append(
                "High memory usage detected. Consider implementing "
                "memory-efficient algorithms or increasing available memory."
            )
        
        # Check circuit depth
        circuit_depth = profile.get_metric(MetricType.CIRCUIT_DEPTH)
        if circuit_depth and circuit_depth.value > 100:
            recommendations.append(
                "Deep quantum circuit detected. Consider circuit "
                "optimization or using error mitigation techniques."
            )
        
        # Check shot count
        shots = profile.get_metric(MetricType.SHOT_COUNT)
        if shots and shots.value > 10000:
            recommendations.append(
                "High shot count may impact performance. Consider "
                "reducing shots or using adaptive sampling."
            )
        
        # Check convergence rate
        convergence = profile.get_metric(MetricType.CONVERGENCE_RATE)
        if convergence and convergence.value < 0.5:
            recommendations.append(
                "Low convergence rate detected. Consider adjusting "
                "optimizer parameters or using different optimization strategies."
            )
        
        return recommendations
    
    def _determine_performance_level(self, profile: PerformanceProfile) -> str:
        """Determine overall performance level."""
        if not profile.metrics:
            return PerformanceLevel.FAIR.value
        
        # Count bottlenecks by severity
        high_severity = 0
        medium_severity = 0
        
        for metric in profile.metrics:
            analysis = self._analyze_metric(metric)
            if analysis.get("is_bottleneck"):
                severity = analysis.get("severity")
                if severity == "high":
                    high_severity += 1
                elif severity == "medium":
                    medium_severity += 1
        
        # Determine performance level
        if high_severity == 0 and medium_severity == 0:
            return PerformanceLevel.EXCELLENT.value
        elif high_severity == 0 and medium_severity <= 1:
            return PerformanceLevel.GOOD.value
        elif high_severity <= 1 and medium_severity <= 2:
            return PerformanceLevel.FAIR.value
        else:
            return PerformanceLevel.POOR.value
    
    def get_aggregate_statistics(self) -> Dict[str, Any]:
        """Get aggregate statistics across all profiles."""
        aggregate = {
            "total_profiles": len(self._profiles),
            "total_metrics": sum(len(p.metrics) for p in self._profiles.values()),
            "metric_types": {},
        }
        
        # Aggregate by metric type
        for metric_type in MetricType:
            stats = self.get_statistics(metric_type)
            if stats:
                aggregate["metric_types"][metric_type.value] = stats
        
        return aggregate
    
    def export_profile(self, profile_id: str, format: str = "json") -> str:
        """Export a performance profile."""
        profile = self.get_profile(profile_id)
        if profile is None:
            raise ValueError(f"Profile {profile_id} not found")
        
        if format == "json":
            return json.dumps(profile.to_dict(), indent=2)
        else:
            raise ValueError(f"Unsupported format: {format}")
    
    def clear_all(self) -> None:
        """Clear all profiles and statistics."""
        self._profiles.clear()
        self._benchmarks.clear()
        self._statistics.clear()
        self._active_profile = None
        logger.info("Cleared all performance data")


# Context manager for profiling
class ProfilingContext:
    """Context manager for automatic profiling."""
    
    def __init__(
        self,
        profiler: PerformanceProfiler,
        profile_id: str,
        name: str,
        auto_record: bool = True
    ):
        self.profiler = profiler
        self.profile_id = profile_id
        self.name = name
        self.auto_record = auto_record
        self.profile: Optional[PerformanceProfile] = None
    
    def __enter__(self) -> "ProfilingContext":
        """Enter profiling context."""
        self.profile = self.profiler.create_profile(self.profile_id, self.name)
        self.profiler.start_profiling(self.profile_id)
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        """Exit profiling context."""
        if self.profile:
            self.profiler.stop_profiling(self.profile_id)
            
            # Auto-record execution time if enabled
            if self.auto_record and self.profile.duration:
                duration_seconds = self.profile.duration.total_seconds()
                self.profiler.record_metric(
                    self.profile_id,
                    MetricType.EXECUTION_TIME,
                    duration_seconds,
                    "s"
                )


# Decorator for profiling functions
def profile_function(
    profiler: PerformanceProfiler,
    profile_id: str,
    name: Optional[str] = None
):
    """Decorator to profile function execution."""
    def decorator(func: Callable) -> Callable:
        async def async_wrapper(*args, **kwargs):
            func_name = name or func.__name__
            
            with ProfilingContext(profiler, profile_id, func_name):
                result = await func(*args, **kwargs)
            
            return result
        
        def sync_wrapper(*args, **kwargs):
            func_name = name or func.__name__
            
            with ProfilingContext(profiler, profile_id, func_name):
                result = func(*args, **kwargs)
            
            return result
        
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper
    
    return decorator


# Factory function
def create_profiler() -> PerformanceProfiler:
    """Create a new performance profiler."""
    return PerformanceProfiler()