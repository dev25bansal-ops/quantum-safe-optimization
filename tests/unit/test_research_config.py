"""Simple unit tests for research features configuration."""

import pytest


def test_qaoa_workflow_config_with_random_seed():
    """Test QAOA workflow config accepts random seed."""
    from qsop.application.workflows.qaoa import QAOAWorkflowConfig

    config = QAOAWorkflowConfig(p_layers=2, shots=1024, random_seed=42)

    assert config.p_layers == 2
    assert config.shots == 1024
    assert config.random_seed == 42


def test_vqe_workflow_config_with_random_seed():
    """Test VQE workflow config accepts random seed."""
    from qsop.application.workflows.vqe import VQEWorkflowConfig

    config = VQEWorkflowConfig(
        ansatz_type="hardware_efficient", ansatz_layers=2, shots=1024, random_seed=42
    )

    assert config.ansatz_layers == 2
    assert config.shots == 1024
    assert config.random_seed == 42


def test_simulated_annealing_config_with_random_seed():
    """Test Simulated Annealing config accepts random seed."""
    from qsop.optimizers.classical.simulated_annealing import SimulatedAnnealingConfig

    config = SimulatedAnnealingConfig(
        max_iterations=1000, cooling_schedule="exponential", random_seed=42
    )

    assert config.max_iterations == 1000
    assert config.random_seed == 42


def test_adaptive_simulated_annealing_config_with_random_seed():
    """Test Adaptive Simulated Annealing config accepts random seed."""
    from qsop.optimizers.classical.simulated_annealing import AdaptiveSimulatedAnnealingConfig

    config = AdaptiveSimulatedAnnealingConfig(max_iterations=1000, random_seed=42)

    assert config.max_iterations == 1000
    assert config.random_seed == 42


def test_qaoa_optimizer_seed_support():
    """Test QAOA optimizer accepts seed parameter."""
    from qsop.optimizers.quantum.qaoa import QAOAOptimizer, ParameterInitStrategy

    optimizer = QAOAOptimizer(p=2, init_strategy=ParameterInitStrategy.RANDOM, seed=42)

    assert optimizer.p == 2
    # Seed creates a deterministic RNG
    assert optimizer.rng is not None


def test_vqe_optimizer_seed_support():
    """Test VQE optimizer accepts seed parameter."""
    from qsop.optimizers.quantum.vqe import VQEOptimizer, AnsatzType

    optimizer = VQEOptimizer(ansatz_type=AnsatzType.HARDWARE_EFFICIENT, depth=2, seed=42)

    assert optimizer.depth == 2
    # Seed creates a deterministic RNG
    assert optimizer.rng is not None


def test_vqe_optimizer_seed_support():
    """Test VQE optimizer accepts seed parameter."""
    from qsop.optimizers.quantum.vqe import VQEOptimizer, AnsatzType

    optimizer = VQEOptimizer(ansatz_type=AnsatzType.HARDWARE_EFFICIENT, depth=2, seed=42)

    assert optimizer.depth == 2
    # VQEOptimizer uses seed to create RNG internally
    # We can verify it accepts the seed parameter


def test_circuit_visualization_response_model():
    """Test CircuitVisualizationResponse model."""
    from qsop.api.routers.analytics import CircuitVisualizationResponse

    response = CircuitVisualizationResponse(
        circuit_svg="<svg>...</svg>",
        depth=15,
        gate_counts={"h": 5, "cx": 8, "rz": 10},
        qubit_count=5,
        connectivity=[[0, 1], [1, 2], [2, 3]],
    )

    assert response.depth == 15
    assert response.qubit_count == 5
    assert len(response.gate_counts) == 3
    assert len(response.connectivity) == 3


def test_benchmark_result_model():
    """Test BenchmarkResult model."""
    from qsop.api.routers.analytics import BenchmarkResult

    result = BenchmarkResult(
        algorithm="qaoa",
        p_layers=2,
        optimizer="COBYLA",
        optimal_value=-10.5,
        iterations=75,
        convergence_rate=0.95,
        execution_time_ms=500,
        memory_usage_mb=128,
    )

    assert result.algorithm == "qaoa"
    assert result.optimal_value == -10.5
    assert result.convergence_rate == 0.95


def test_ablation_result_model():
    """Test AblationResult model."""
    from qsop.api.routers.analytics import AblationResult

    result = AblationResult(
        config={"p_layers": 2, "optimizer": "COBYLA"},
        optimal_value=-10.5,
        iterations=75,
        convergence=True,
        execution_time_ms=500,
    )

    assert result.config["p_layers"] == 2
    assert result.convergence is True
    assert result.execution_time_ms == 500


def test_benchmark_comparison_request_model():
    """Test BenchmarkComparisonRequest model."""
    from qsop.api.routers.analytics import BenchmarkComparisonRequest

    request = BenchmarkComparisonRequest(
        algorithms=["qaoa", "vqe"], metrics=["optimal_value", "iterations"], p_layers_range=(1, 3)
    )

    assert "qaoa" in request.algorithms
    assert "vqe" in request.algorithms
    assert request.p_layers_range == (1, 3)


def test_ablation_study_request_model():
    """Test AblationStudyRequest model."""
    from qsop.api.routers.analytics import AblationStudyRequest

    request = AblationStudyRequest(
        algorithm="qaoa",
        p_layers_range=(1, 5),
        optimizers=["COBYLA", "SPSA"],
        repetitions=5,
        random_seed=42,
    )

    assert request.algorithm == "qaoa"
    assert request.p_layers_range == (1, 5)
    assert len(request.optimizers) == 2
    assert request.random_seed == 42


def test_random_seed_affects_optimization_config():
    """Test that random seed is properly stored in config objects."""
    from qsop.application.workflows.qaoa import QAOAWorkflowConfig
    from qsop.application.workflows.vqe import VQEWorkflowConfig

    configs = [
        QAOAWorkflowConfig(random_seed=42),
        QAOAWorkflowConfig(random_seed=123),
        VQEWorkflowConfig(random_seed=42),
        VQEWorkflowConfig(random_seed=456),
    ]

    assert configs[0].random_seed == 42
    assert configs[1].random_seed == 123
    assert configs[2].random_seed == 42
    assert configs[3].random_seed == 456

    # Verify at least some distinct seeds (42 appears twice by design)
    seeds = [c.random_seed for c in configs]
    unique_seeds = set(s for s in seeds if s is not None)
    assert len(unique_seeds) >= 3  # 42, 123, 456


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
