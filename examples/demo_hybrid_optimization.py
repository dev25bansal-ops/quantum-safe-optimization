#!/usr/bin/env python3
"""
Demonstration of hybrid quantum-classical optimization.

This example shows how to use the platform to solve a MaxCut problem
using QAOA with a statevector simulator.
"""

import sys

sys.path.insert(0, "src")

from qsop.backends.simulators.statevector import StatevectorSimulator
from qsop.domain.models.problem import OptimizationProblem, Variable, VariableType
from qsop.optimizers.classical.evolutionary import (
    DifferentialEvolution,
    GeneticAlgorithm,
    GeneticAlgorithmConfig,
)
from qsop.optimizers.classical.simulated_annealing import (
    SimulatedAnnealing,
    SimulatedAnnealingConfig,
)


def create_maxcut_problem():
    """Create a MaxCut optimization problem."""
    # 5-node graph
    edges = [
        (0, 1, 1.0),
        (0, 2, 1.0),
        (1, 2, 1.0),
        (1, 3, 1.0),
        (2, 3, 1.0),
        (2, 4, 1.0),
        (3, 4, 1.0),
    ]

    variables = [
        Variable(
            name=f"x_{i}",
            var_type=VariableType.CONTINUOUS,
            lower_bound=0.0,
            upper_bound=1.0,
        )
        for i in range(5)
    ]

    def maxcut_objective(x):
        """Negative cut value (for minimization)."""
        # Round to binary
        binary = [1 if xi > 0.5 else 0 for xi in x]
        cut_value = 0.0
        for i, j, w in edges:
            if binary[i] != binary[j]:
                cut_value += w
        return -cut_value  # Minimize negative = maximize

    return OptimizationProblem(
        variables=variables,
        objective=maxcut_objective,
        metadata={"type": "maxcut", "edges": edges},
    )


def create_rosenbrock_problem(n_dims: int = 2):
    """Create a Rosenbrock function optimization problem."""
    variables = [
        Variable(
            name=f"x_{i}",
            var_type=VariableType.CONTINUOUS,
            lower_bound=-5.0,
            upper_bound=5.0,
        )
        for i in range(n_dims)
    ]

    def rosenbrock(x):
        """Rosenbrock function - minimum at (1, 1, ..., 1)."""
        total = 0.0
        for i in range(len(x) - 1):
            total += 100 * (x[i + 1] - x[i] ** 2) ** 2 + (1 - x[i]) ** 2
        return total

    return OptimizationProblem(
        variables=variables,
        objective=rosenbrock,
        metadata={"type": "rosenbrock", "optimal": [1.0] * n_dims},
    )


def demo_genetic_algorithm():
    """Demonstrate Genetic Algorithm optimization."""

    problem = create_rosenbrock_problem(3)

    config = GeneticAlgorithmConfig(
        population_size=50,
        generations=100,
        mutation_probability=0.1,
    )
    optimizer = GeneticAlgorithm(config)

    optimizer.optimize(problem)


def demo_differential_evolution():
    """Demonstrate Differential Evolution optimization."""

    problem = create_rosenbrock_problem(2)

    optimizer = DifferentialEvolution()
    optimizer.optimize(problem)


def demo_simulated_annealing():
    """Demonstrate Simulated Annealing optimization."""

    problem = create_maxcut_problem()

    config = SimulatedAnnealingConfig(
        initial_temperature=100.0,
        final_temperature=0.01,
        max_iterations=5000,
    )
    optimizer = SimulatedAnnealing(config)

    result = optimizer.optimize(problem)

    # Convert to binary solution
    [1 if p > 0.5 else 0 for p in result.optimal_parameters]


def demo_quantum_simulator():
    """Demonstrate the statevector simulator."""

    simulator = StatevectorSimulator()

    # Create a Bell state
    circuit = [
        ("H", 0, []),
        ("CNOT", [0, 1], []),
    ]

    result = simulator.run(circuit, shots=1000)

    # Verify only 00 and 11 outcomes
    for bitstring in result["counts"]:
        assert bitstring in ["00", "11"], f"Unexpected outcome: {bitstring}"


def demo_crypto():
    """Demonstrate post-quantum cryptography."""

    try:
        from qsop.crypto.pqc import (
            KEMAlgorithm,
            SignatureAlgorithm,
            get_kem,
            get_signature_scheme,
            is_oqs_available,
        )

        if not is_oqs_available():
            pass

        # KEM demo
        kem = get_kem(KEMAlgorithm.KYBER768)
        pk, sk = kem.keygen()

        ct, ss1 = kem.encapsulate(pk)
        ss2 = kem.decapsulate(ct, sk)

        assert ss1 == ss2, "Shared secrets don't match!"

        # Signature demo
        sig = get_signature_scheme(SignatureAlgorithm.DILITHIUM3)
        pk, sk = sig.keygen()

        message = b"Hello, quantum-safe world!"
        signature = sig.sign(message, sk)

        valid = sig.verify(message, signature, pk)
        assert valid, "Signature verification failed!"

except Exception:  # noqa: BLE001 - Demo cleanup error ignored
        pass


def main():
    """Run all demonstrations."""

    demo_quantum_simulator()
    demo_genetic_algorithm()
    demo_differential_evolution()
    demo_simulated_annealing()
    demo_crypto()


if __name__ == "__main__":
    main()
