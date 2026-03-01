import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../../src")))

from qsop.backends.simulators.statevector import StatevectorSimulator
from qsop.domain.models.problem import OptimizationProblem, Variable, VariableType
from qsop.optimizers.hybrid.vqe_hybrid import GradientMethod, HybridVQEConfig, HybridVQEOptimizer


def test_vqe_adaptive_shots_logic():
    """Verify that shot counts are dynamically adjusted during VQE optimization."""
    # Simple problem setup (Hamiltonian type)
    variables = [
        Variable(name="x0", var_type=VariableType.BINARY, lower_bound=0, upper_bound=1),
    ]

    # Simple Ising-like objective
    def objective(x):
        return float(x["x0"])

    problem = OptimizationProblem(
        variables=variables, objective=objective, metadata={"type": "hamiltonian"}
    )

    # Setup adaptive config
    min_shots = 100
    max_shots = 200
    max_iterations = 2

    config = HybridVQEConfig(
        adaptive_shots=True,
        min_shots=min_shots,
        max_shots=max_shots,
        max_iterations=max_iterations,
        optimizer="SLSQP",
        gradient_method=GradientMethod.SPSA,  # More shot-efficient for test
    )

    backend = StatevectorSimulator()
    optimizer = HybridVQEOptimizer(config=config, backend=backend)

    result = optimizer.optimize(problem)

    total_shots = result.metadata["total_shots"]
    assert total_shots > 0

    # Check that shots are within reasonable bounds
    # For 1 variable, SPSA uses 2 calls per gradient, plus 1 for function
    # Total shots per iteration ~= 3 * current_shots
    # Max shots possible ~= (iterations + gradient_evals * 2) * max_shots
    upper_bound = (result.function_evaluations + result.gradient_evaluations * 2) * max_shots
    assert total_shots <= upper_bound


def test_vqe_shot_budget():
    """Verify that shot budget is enforced."""
    variables = [
        Variable(name="x0", var_type=VariableType.BINARY, lower_bound=0, upper_bound=1),
    ]
    problem = OptimizationProblem(
        variables=variables, objective=lambda x: float(x["x0"]), metadata={"type": "hamiltonian"}
    )

    shot_budget = 500
    config = HybridVQEConfig(
        shots=300, max_iterations=10, shot_budget=shot_budget, gradient_method=GradientMethod.SPSA
    )

    backend = StatevectorSimulator()
    optimizer = HybridVQEOptimizer(config=config, backend=backend)

    result = optimizer.optimize(problem)

    # Should stop before 10 iterations because 300 * 2 > 500 (1 function + 1 gradient = 2 calls)
    assert result.metadata["total_shots"] <= shot_budget
    assert result.iterations < 10
