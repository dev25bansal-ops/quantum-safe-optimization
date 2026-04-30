"""
Performance Benchmarking Suite for Quantum-Safe Optimization Platform.

Comprehensive performance tests including:
- API response time benchmarks
- Database operation benchmarks
- Caching performance tests
- Load testing scenarios
- Memory usage profiling
"""

import pytest
import asyncio
import time
import sys
from datetime import datetime
from typing import Dict, Any, List
from dataclasses import dataclass, field


@dataclass
class BenchmarkResult:
    """Benchmark result data."""
    name: str
    operation: str
    iterations: int
    total_time: float
    avg_time: float
    min_time: float
    max_time: float
    ops_per_second: float
    timestamp: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "operation": self.operation,
            "iterations": self.iterations,
            "total_time": self.total_time,
            "avg_time": self.avg_time,
            "min_time": self.min_time,
            "max_time": self.max_time,
            "ops_per_second": self.ops_per_second,
            "timestamp": self.timestamp.isoformat(),
        }


class PerformanceBenchmark:
    """Performance benchmark runner."""

    def __init__(self):
        self.results: List[BenchmarkResult] = []

    def run_benchmark(
        self,
        name: str,
        operation: str,
        func,
        iterations: int = 100
    ) -> BenchmarkResult:
        """Run a benchmark for a synchronous function."""
        times = []

        for _ in range(iterations):
            start = time.perf_counter()
            func()
            end = time.perf_counter()
            times.append(end - start)

        total_time = sum(times)
        avg_time = total_time / iterations

        result = BenchmarkResult(
            name=name,
            operation=operation,
            iterations=iterations,
            total_time=total_time,
            avg_time=avg_time,
            min_time=min(times),
            max_time=max(times),
            ops_per_second=iterations / total_time
        )

        self.results.append(result)
        return result

    async def run_benchmark_async(
        self,
        name: str,
        operation: str,
        func,
        iterations: int = 100
    ) -> BenchmarkResult:
        """Run a benchmark for an asynchronous function."""
        times = []

        for _ in range(iterations):
            start = time.perf_counter()
            await func()
            end = time.perf_counter()
            times.append(end - start)

        total_time = sum(times)
        avg_time = total_time / iterations

        result = BenchmarkResult(
            name=name,
            operation=operation,
            iterations=iterations,
            total_time=total_time,
            avg_time=avg_time,
            min_time=min(times),
            max_time=max(times),
            ops_per_second=iterations / total_time
        )

        self.results.append(result)
        return result

    def get_summary(self) -> Dict[str, Any]:
        """Get summary of all benchmark results."""
        if not self.results:
            return {"benchmarks": [], "total": 0}

        return {
            "benchmarks": [r.to_dict() for r in self.results],
            "total": len(self.results),
            "total_time": sum(r.total_time for r in self.results),
        }


# ===========================
# Input Validation Benchmarks
# ===========================

def benchmark_string_validation():
    """Benchmark string validation performance."""
    from api.security.input_validation import InputValidator, SecurityLevel

    def validate():
        InputValidator.validate_string(
            "test_value_123",
            field_name="test_field",
            max_length=100,
            security_level=SecurityLevel.MODERATE
        )

    return validate


def benchmark_integer_validation():
    """Benchmark integer validation performance."""
    from api.security.input_validation import InputValidator

    def validate():
        InputValidator.validate_integer(
            42,
            field_name="test_field",
            min_value=0,
            max_value=100
        )

    return validate


# ===========================
# Cache Benchmarks
# ===========================

async def benchmark_cache_set_get():
    """Benchmark cache set and get operations."""
    from api.cache.cache import LocalMemoryCache

    cache = LocalMemoryCache(max_size=1000)

    async def cache_ops():
        await cache.set("test_key", "test_value")
        await cache.get("test_key")

    return cache_ops


async def benchmark_cache_multi_level():
    """Benchmark multi-level cache operations."""
    from api.cache.cache import LocalMemoryCache, MultiLevelCache

    l1_cache = LocalMemoryCache(max_size=100)
    l2_cache = LocalMemoryCache(max_size=1000)
    cache = MultiLevelCache(l1_cache, l2_cache)

    async def cache_ops():
        await cache.set("test_key", "test_value")
        await cache.get("test_key")

    return cache_ops


# ===========================
# Connection Pool Benchmarks
# ===========================

async def benchmark_connection_pool():
    """Benchmark connection pool performance."""
    from api.db.connection_pool import ConnectionPool, ConnectionPoolConfig

    class MockConn:
        async def ping(self):
            return True

    async def factory():
        return MockConn()

    config = ConnectionPoolConfig(min_connections=2, max_connections=10)
    pool = ConnectionPool(factory, config)
    await pool.initialize()

    async def pool_ops():
        async with pool.connection() as conn:
            pass

    return pool_ops


# ===========================
# DI Container Benchmarks
# ===========================

def benchmark_di_registration():
    """Benchmark dependency injection registration."""
    from api.di_container import DIContainer

    container = DIContainer()

    def register():
        container.register_singleton(object, lambda: object())
        container.resolve(object)

    return register


def benchmark_di_resolution():
    """Benchmark dependency injection resolution."""
    from api.di_container import DIContainer

    container = DIContainer()
    container.register_singleton(object, lambda: object())

    def resolve():
        container.resolve(object)

    return resolve


# ===========================
# Configuration Benchmarks
# ===========================

def benchmark_config_loading():
    """Benchmark configuration loading."""
    from api.config import AppConfig

    def load_config():
        AppConfig.from_env()

    return load_config


# ===========================
# Quantum ML Benchmarks
# ===========================

def benchmark_quantum_feature_map():
    """Benchmark quantum feature mapping."""
    from src.qsop.optimizers.quantum.quantum_ml import QuantumFeatureMap, FeatureMapType
    import numpy as np

    feature_map = QuantumFeatureMap(num_qubits=4, feature_map_type=FeatureMapType.PAULI)
    features = np.random.rand(4)

    def encode():
        feature_map.encode(features)

    return encode


def benchmark_qnn_forward():
    """Benchmark quantum neural network forward pass."""
    from src.qsop.optimizers.quantum.quantum_ml import QuantumNeuralNetwork, QMLModelConfig, QMLModelType
    import numpy as np

    config = QMLModelConfig(
        model_type=QMLModelType.QUANTUM_NEURAL_NETWORK,
        num_qubits=4,
        num_layers=2
    )

    qnn = QuantumNeuralNetwork(config)
    features = np.random.rand(4)

    def forward():
        qnn.forward(features)

    return forward


# ===========================
# Run All Benchmarks
# ===========================

def run_all_benchmarks():
    """Run all benchmarks and generate report."""
    import asyncio

    benchmark = PerformanceBenchmark()
    results = []

    print("\n" + "="*60)
    print("Quantum-Safe Optimization Platform - Performance Benchmarks")
    print("="*60 + "\n")

    # String validation
    print("Running string validation benchmark...")
    result = benchmark.run_benchmark(
        "String Validation",
        "validate_string",
        benchmark_string_validation(),
        iterations=1000
    )
    print(f"  Avg: {result.avg_time*1000:.3f}ms, Ops/sec: {result.ops_per_second:.0f}")
    results.append(result)

    # Integer validation
    print("Running integer validation benchmark...")
    result = benchmark.run_benchmark(
        "Integer Validation",
        "validate_integer",
        benchmark_integer_validation(),
        iterations=1000
    )
    print(f"  Avg: {result.avg_time*1000:.3f}ms, Ops/sec: {result.ops_per_second:.0f}")
    results.append(result)

    # Cache operations
    print("Running cache benchmark...")
    cache_benchmark = asyncio.run(benchmark_cache_set_get())
    result = benchmark.run_benchmark(
        "Cache Operations",
        "cache_set_get",
        asyncio.run(benchmark_cache_set_get()),
        iterations=100
    )
    print(f"  Avg: {result.avg_time*1000:.3f}ms, Ops/sec: {result.ops_per_second:.0f}")
    results.append(result)

    # DI resolution
    print("Running DI resolution benchmark...")
    result = benchmark.run_benchmark(
        "DI Resolution",
        "resolve_dependency",
        benchmark_di_resolution(),
        iterations=1000
    )
    print(f"  Avg: {result.avg_time*1000:.3f}ms, Ops/sec: {result.ops_per_second:.0f}")
    results.append(result)

    # Config loading
    print("Running config loading benchmark...")
    result = benchmark.run_benchmark(
        "Config Loading",
        "load_config",
        benchmark_config_loading(),
        iterations=100
    )
    print(f"  Avg: {result.avg_time*1000:.3f}ms, Ops/sec: {result.ops_per_second:.0f}")
    results.append(result)

    # Quantum feature map
    print("Running quantum feature map benchmark...")
    result = benchmark.run_benchmark(
        "Quantum Feature Map",
        "encode_features",
        benchmark_quantum_feature_map(),
        iterations=100
    )
    print(f"  Avg: {result.avg_time*1000:.3f}ms, Ops/sec: {result.ops_per_second:.0f}")
    results.append(result)

    # QNN forward pass
    print("Running QNN forward pass benchmark...")
    result = benchmark.run_benchmark(
        "QNN Forward",
        "forward_pass",
        benchmark_qnn_forward(),
        iterations=10
    )
    print(f"  Avg: {result.avg_time*1000:.3f}ms, Ops/sec: {result.ops_per_second:.1f}")
    results.append(result)

    # Summary
    print("\n" + "="*60)
    print("BENCHMARK SUMMARY")
    print("="*60)

    for result in results:
        print(f"{result.name}: {result.avg_time*1000:.3f}ms avg, {result.ops_per_second:.0f} ops/sec")

    print("\n" + "="*60)

    return benchmark.get_summary()


if __name__ == "__main__":
    run_all_benchmarks()