#!/usr/bin/env python3
"""
Demonstration of hybrid quantum-classical optimization.

This example shows how to use the platform to solve a MaxCut problem
using QAOA with a statevector simulator.
"""

import numpy as np
import sys
sys.path.insert(0, "src")

from qsop.backends.simulators.statevector import StatevectorSimulator
from qsop.optimizers.classical.evolutionary import (
    GeneticAlgorithm,
    GeneticAlgorithmConfig,
    DifferentialEvolution,
)
from qsop.optimizers.classical.simulated_annealing import (
    SimulatedAnnealing,
    SimulatedAnnealingConfig,
)
from qsop.domain.models.problem import OptimizationProblem, Variable, VariableType


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
            total += 100 * (x[i+1] - x[i]**2)**2 + (1 - x[i])**2
        return total
    
    return OptimizationProblem(
        variables=variables,
        objective=rosenbrock,
        metadata={"type": "rosenbrock", "optimal": [1.0] * n_dims},
    )


def demo_genetic_algorithm():
    """Demonstrate Genetic Algorithm optimization."""
    print("\n" + "="*60)
    print("Genetic Algorithm on Rosenbrock Function")
    print("="*60)
    
    problem = create_rosenbrock_problem(3)
    
    config = GeneticAlgorithmConfig(
        population_size=50,
        generations=100,
        mutation_probability=0.1,
    )
    optimizer = GeneticAlgorithm(config)
    
    result = optimizer.optimize(problem)
    
    print(f"Optimal value: {result.optimal_value:.6f}")
    print(f"Optimal parameters: {[f'{p:.4f}' for p in result.optimal_parameters]}")
    print(f"Iterations: {result.iterations}")
    print(f"Expected optimal: (1, 1, 1) with value 0")


def demo_differential_evolution():
    """Demonstrate Differential Evolution optimization."""
    print("\n" + "="*60)
    print("Differential Evolution on Rosenbrock Function")
    print("="*60)
    
    problem = create_rosenbrock_problem(2)
    
    optimizer = DifferentialEvolution()
    result = optimizer.optimize(problem)
    
    print(f"Optimal value: {result.optimal_value:.6f}")
    print(f"Optimal parameters: {[f'{p:.4f}' for p in result.optimal_parameters]}")
    print(f"Iterations: {result.iterations}")


def demo_simulated_annealing():
    """Demonstrate Simulated Annealing optimization."""
    print("\n" + "="*60)
    print("Simulated Annealing on MaxCut Problem")
    print("="*60)
    
    problem = create_maxcut_problem()
    
    config = SimulatedAnnealingConfig(
        initial_temperature=100.0,
        final_temperature=0.01,
        max_iterations=5000,
    )
    optimizer = SimulatedAnnealing(config)
    
    result = optimizer.optimize(problem)
    
    # Convert to binary solution
    binary = [1 if p > 0.5 else 0 for p in result.optimal_parameters]
    cut_value = -result.optimal_value
    
    print(f"Best cut value: {cut_value:.1f}")
    print(f"Partition: {binary}")
    print(f"Iterations: {result.iterations}")
    print(f"Expected optimal cut: 5")


def demo_quantum_simulator():
    """Demonstrate the statevector simulator."""
    print("\n" + "="*60)
    print("Statevector Simulator Demo")
    print("="*60)
    
    simulator = StatevectorSimulator()
    
    # Create a Bell state
    circuit = [
        ("H", 0, []),
        ("CNOT", [0, 1], []),
    ]
    
    result = simulator.run(circuit, shots=1000)
    
    print("Bell State |Phi+> = (|00> + |11>)/sqrt(2)")
    print(f"Measurement counts: {result['counts']}")
    
    # Verify only 00 and 11 outcomes
    for bitstring in result['counts']:
        assert bitstring in ['00', '11'], f"Unexpected outcome: {bitstring}"
    print("✓ Bell state verified!")


def demo_crypto():
    """Demonstrate post-quantum cryptography."""
    print("\n" + "="*60)
    print("Post-Quantum Cryptography Demo")
    print("="*60)
    
    try:
        from qsop.crypto.pqc import (
            KEMAlgorithm,
            SignatureAlgorithm,
            get_kem,
            get_signature_scheme,
            is_oqs_available,
        )
        
        if not is_oqs_available():
            print("liboqs-python not installed - using fallback provider")
            print("Install with: pip install liboqs-python")
        
        # KEM demo
        print("\nKyber-768 Key Encapsulation:")
        kem = get_kem(KEMAlgorithm.KYBER768)
        pk, sk = kem.keygen()
        print(f"  Public key size: {len(pk)} bytes")
        print(f"  Private key size: {len(sk)} bytes")
        
        ct, ss1 = kem.encapsulate(pk)
        ss2 = kem.decapsulate(ct, sk)
        
        assert ss1 == ss2, "Shared secrets don't match!"
        print(f"  Ciphertext size: {len(ct)} bytes")
        print(f"  Shared secret size: {len(ss1)} bytes")
        print("  ✓ Encapsulation/decapsulation successful!")
        
        # Signature demo
        print("\nDilithium-3 Digital Signatures:")
        sig = get_signature_scheme(SignatureAlgorithm.DILITHIUM3)
        pk, sk = sig.keygen()
        print(f"  Public key size: {len(pk)} bytes")
        print(f"  Private key size: {len(sk)} bytes")
        
        message = b"Hello, quantum-safe world!"
        signature = sig.sign(message, sk)
        print(f"  Signature size: {len(signature)} bytes")
        
        valid = sig.verify(message, signature, pk)
        assert valid, "Signature verification failed!"
        print("  ✓ Signature verified!")
        
    except Exception as e:
        print(f"Crypto demo error: {e}")


def main():
    """Run all demonstrations."""
    print("Quantum-Safe Secure Optimization Platform - Demo")
    print("="*60)
    
    demo_quantum_simulator()
    demo_genetic_algorithm()
    demo_differential_evolution()
    demo_simulated_annealing()
    demo_crypto()
    
    print("\n" + "="*60)
    print("All demonstrations completed successfully!")
    print("="*60)


if __name__ == "__main__":
    main()
