"""Integration tests for hybrid optimization workflows."""

import numpy as np
import pytest

from qsop.application.workflows.hybrid_loop import (
    HybridLoopConfig,
    HybridOptimizationLoop,
    LoopStatus,
)
from qsop.backends.simulators.statevector import StatevectorSimulator
from qsop.domain.models.problem import (
    OptimizationProblem,
    Variable,
    VariableType,
)


class TestHybridOptimizationLoop:
    """Test the generic hybrid optimization loop."""

    @pytest.fixture
    def simple_problem(self):
        """Create a simple test problem."""
        variables = [
            Variable(
                name="theta", var_type=VariableType.CONTINUOUS, lower_bound=0, upper_bound=2 * np.pi
            ),
            Variable(
                name="phi", var_type=VariableType.CONTINUOUS, lower_bound=0, upper_bound=2 * np.pi
            ),
        ]

        def objective(x):
            # x is a dict with variable names as keys
            return np.sin(x["theta"]) ** 2 + np.cos(x["phi"]) ** 2

        return OptimizationProblem(
            variables=variables,
            objective=objective,
        )

    def test_loop_runs_to_completion(self, simple_problem):
        """Test that the loop completes successfully."""
        config = HybridLoopConfig(
            max_iterations=20,
            convergence_threshold=1e-4,
        )

        loop = HybridOptimizationLoop(config=config)

        # Simple evaluator (no actual quantum circuit)
        def quantum_evaluator(params):
            cost = simple_problem.evaluate(params.tolist())
            return {"counts": {"0": 1}, "shots": 1}, cost

        # Simple classical update (gradient-free)
        def classical_updater(params, cost, history):
            # Random perturbation
            return params + np.random.normal(0, 0.1, size=len(params))

        initial_params = np.array([1.0, 1.0])

        result = loop.run(
            simple_problem,
            quantum_evaluator,
            classical_updater,
            initial_params,
        )

        assert result is not None
        assert result.iterations > 0
        assert loop.status in [LoopStatus.MAX_ITERATIONS, LoopStatus.CONVERGED]

    def test_loop_tracks_history(self, simple_problem):
        """Test that history is tracked."""
        config = HybridLoopConfig(max_iterations=10)
        loop = HybridOptimizationLoop(config=config)

        def quantum_evaluator(params):
            cost = simple_problem.evaluate(params.tolist())
            return {}, cost

        def classical_updater(params, cost, history):
            return params * 0.99  # Simple decay

        result = loop.run(
            simple_problem,
            quantum_evaluator,
            classical_updater,
            np.array([1.0, 1.0]),
        )

        assert len(result.objective_history) > 0
        assert len(result.objective_history) == result.iterations

    def test_callback_stops_loop(self, simple_problem):
        """Test that callback can stop the loop."""
        config = HybridLoopConfig(max_iterations=100)
        loop = HybridOptimizationLoop(config=config)

        stop_at = 5

        def stop_callback(iteration, cost, params):
            return iteration < stop_at

        loop.add_callback(stop_callback)

        def quantum_evaluator(params):
            return {}, 1.0

        def classical_updater(params, cost, history):
            return params

        result = loop.run(
            simple_problem,
            quantum_evaluator,
            classical_updater,
            np.array([1.0, 1.0]),
        )

        assert result.iterations <= stop_at + 1
        assert loop.status == LoopStatus.STOPPED

    def test_checkpointing(self, simple_problem):
        """Test checkpoint creation."""
        config = HybridLoopConfig(
            max_iterations=25,
            checkpoint_interval=10,
        )
        loop = HybridOptimizationLoop(config=config)

        def quantum_evaluator(params):
            return {}, np.sum(params**2)

        def classical_updater(params, cost, history):
            return params * 0.9

        loop.run(
            simple_problem,
            quantum_evaluator,
            classical_updater,
            np.array([5.0, 5.0]),
        )

        checkpoints = loop.get_checkpoints()
        assert len(checkpoints) >= 2  # Should have multiple checkpoints


class TestEndToEndOptimization:
    """End-to-end optimization tests."""

    @pytest.fixture
    def simulator(self):
        """Create simulator backend."""
        return StatevectorSimulator()

    def test_optimization_with_simulator(self, simulator):
        """Test optimization using the statevector simulator."""
        # Create a simple problem
        variables = [
            Variable(name="x", var_type=VariableType.CONTINUOUS, lower_bound=-2, upper_bound=2),
        ]

        def objective(x):
            # x is a dict with variable names as keys
            return (x["x"] - 0.5) ** 2

        problem = OptimizationProblem(variables=variables, objective=objective)

        # Simple "quantum" evaluation using simulator
        def quantum_evaluator(params):
            # Just run a simple circuit
            circuit = [("RY", 0, [params[0]]), ("MEASURE", 0, [])]
            result = simulator.run(circuit, shots=100)

            # Cost based on measurement
            counts = result.counts
            prob_1 = counts.get("1", 0) / 100
            cost = problem.evaluate([prob_1 * 4 - 2])  # Map to [-2, 2]

            return result, cost

        # Gradient-free update
        def classical_updater(params, cost, history):
            if len(history) < 2:
                return params + np.random.normal(0, 0.2, size=len(params))

            # Simple momentum
            prev_params = np.array(history[-2]["params"])
            momentum = params - prev_params
            return params + 0.5 * momentum + np.random.normal(0, 0.1, size=len(params))

        config = HybridLoopConfig(max_iterations=30)
        loop = HybridOptimizationLoop(config=config, backend=simulator)

        result = loop.run(
            problem,
            quantum_evaluator,
            classical_updater,
            np.array([1.0]),
        )

        assert result is not None
        assert result.optimal_value < 1.0  # Should find something reasonable


class TestSecureJobWorkflow:
    """Test secure job submission workflow."""

    def test_encrypt_and_sign_job(self):
        """Test encrypting and signing a job specification."""
        from qsop.application.services.crypto_service import (
            CryptoPolicy,
            CryptoService,
            SecureJobHandler,
        )
        from qsop.crypto.pqc import KEMAlgorithm, SignatureAlgorithm

        # Create crypto service
        policy = CryptoPolicy(
            kem_algorithm=KEMAlgorithm.KYBER768,
            signature_algorithm=SignatureAlgorithm.DILITHIUM3,
        )
        crypto = CryptoService(policy=policy)

        # Generate keys
        crypto.generate_kem_keypair("tenant-1")
        crypto.generate_signing_keypair("platform-sign")

        # Create job spec
        job_spec = {
            "job_id": "job-123",
            "algorithm": "qaoa",
            "problem_type": "maxcut",
            "parameters": {"p_layers": 2, "shots": 1024},
        }

        # Secure the job
        handler = SecureJobHandler(crypto)
        secured = handler.secure_job_spec(
            job_spec,
            tenant_key_id="tenant-1",
            platform_sign_key_id="platform-sign",
        )

        assert "envelope" in secured
        assert "signature" in secured

        # Unsecure and verify
        recovered_spec, is_valid = handler.unsecure_job_spec(
            secured,
            tenant_key_id="tenant-1",
        )

        assert is_valid is True
        assert recovered_spec["job_id"] == "job-123"
        assert recovered_spec["algorithm"] == "qaoa"
