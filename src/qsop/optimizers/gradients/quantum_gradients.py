"""
Quantum Gradient Computation Module.

Implements various gradient estimation methods for variational quantum algorithms:
- Parameter Shift Rule (exact for Pauli rotations)
- SPSA (Simultaneous Perturbation Stochastic Approximation)
- Finite Difference Methods
- Natural Gradients (Quantum Fisher Information)

Based on: Mari et al., "Evaluating analytic gradients on quantum hardware",
           Phys. Rev. Lett. 2021.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import TYPE_CHECKING, Sequence

import numpy as np

if TYPE_CHECKING:
    from numpy.typing import NDArray
    from qiskit import QuantumCircuit
    from qiskit_aer import AerSimulator


class QuantumGradientEstimator(ABC):
    """Abstract base class for quantum gradient estimators."""

    @abstractmethod
    def compute_gradient(
        self,
        circuit_builder: callable,
        params: NDArray[np.float64],
        observable: callable,
        backend: "AerSimulator",
    ) -> NDArray[np.float64]:
        """
        Compute gradient of expectation value with respect to parameters.

        Args:
            circuit_builder: Function that builds circuit given parameters
            params: Current parameter values
            observable: Function that computes expectation from measurements
            backend: Quantum backend

        Returns:
            Gradient vector (∂⟨O⟩/∂θ₀, ∂⟨O⟩/∂θ₁, ...)
        """
        pass


class ParameterShiftGradient(QuantumGradientEstimator):
    """
    Parameter Shift Rule gradient estimator.

    For circuits composed of Pauli rotation gates Rx, Ry, Rz, the gradient
    can be computed exactly using:
        ∂⟨O⟩/∂θ = (⟨O(θ + s)⟩ - ⟨O(θ - s)⟩) / 2

    where s = π/4 is the shift parameter.

    This provides exact gradients without finite-difference approximation error.
    """

    def __init__(self, shift: float = np.pi / 4):
        """
        Initialize parameter shift gradient.

        Args:
            shift: Shift parameter (default: π/4)
        """
        self.shift = shift

    def compute_gradient(
        self,
        circuit_builder: callable,
        params: NDArray[np.float64],
        observable: callable,
        backend: "AerSimulator",
    ) -> NDArray[np.float64]:
        """
        Compute gradient using parameter shift rule.

        Args:
            circuit_builder: Function QuantumCircuit(ndarray) -> QuantumCircuit
            params: Current parameter values [θ₀, θ₁, ..., θₙ]
            observable: Function that takes circuit, backend and returns expectation
            backend: Quantum backend for execution

        Returns:
            Gradient vector ∇θ⟨O⟩
        """
        n_params = len(params)
        gradient = np.zeros(n_params, dtype=np.float64)

        for i in range(n_params):
            # Create parameter-shifted versions
            params_plus = params.copy()
            params_plus[i] += self.shift

            params_minus = params.copy()
            params_minus[i] -= self.shift

            # Build circuits
            circuit_plus = circuit_builder(params_plus)
            circuit_minus = circuit_builder(params_minus)

            # Compute expectation values
            exp_plus = observable(circuit_plus, backend)
            exp_minus = observable(circuit_minus, backend)

            # Parameter shift rule: ∂⟨O⟩/∂θᵢ = (⟨O(θ+s)⟩ - ⟨O(θ-s)⟩) / 2
            gradient[i] = (exp_plus - exp_minus) / 2.0

        return gradient

    def compute_gradient_vectorized(
        self,
        circuit_builder: callable,
        params: NDArray[np.float64],
        observable: callable,
        backend: "AerSimulator",
        batch_size: int = 4,
    ) -> NDArray[np.float64]:
        """
        Compute gradient using parameter shift rule with vectorized execution.

        Args:
            circuit_builder: Function that builds circuit given parameters
            params: Current parameter values
            observable: Function that computes expectation from measurements
            backend: Quantum backend
            batch_size: Number of circuits to execute in batch

        Returns:
            Gradient vector
        """
        n_params = len(params)
        gradient = np.zeros(n_params, dtype=np.float64)

        # Process in batches
        for start_idx in range(0, n_params, batch_size):
            end_idx = min(start_idx + batch_size, n_params)

            # Collect circuits for this batch
            plus_circuits = []
            minus_circuits = []

            for i in range(start_idx, end_idx):
                params_plus = params.copy()
                params_plus[i] += self.shift
                plus_circuits.append(circuit_builder(params_plus))

                params_minus = params.copy()
                params_minus[i] -= self.shift
                minus_circuits.append(circuit_builder(params_minus))

            # Execute batch (simplified - in production use transpile with batch optimization)
            for i, circuit in enumerate(plus_circuits):
                exp_plus = observable(circuit, backend)
                circuit = minus_circuits[i]
                exp_minus = observable(circuit, backend)

                gradient[start_idx + i] = (exp_plus - exp_minus) / 2.0

        return gradient


class SPSAGradient(QuantumGradientEstimator):
    """
    Simultaneous Perturbation Stochastic Approximation (SPSA) gradient.

    SPSA estimates all gradient components simultaneously using only 2 circuit
    evaluations regardless of parameter count, making it highly efficient
    for high-dimensional parameter spaces.

    Based on: Spall, "Introduction to Stochastic Search and Optimization",
               Wiley 2003.
    """

    def __init__(
        self,
        perturbation: NDArray[np.float64] | float | None = None,
        gain_a: float = 1.0,
        gain_c: float = 0.1,
        alpha: float = 0.602,
        gamma: float = 0.101,
    ):
        """
        Initialize SPSA gradient estimator.

        Args:
            perturbation: Initial perturbation vector or scalar
            gain_a: Gain parameter for gradient estimation
            gain_c: Gain parameter for perturbation size
            alpha: Exponent for gain_a decay
            gamma: Exponent for gain_c decay
        """
        self.perturbation = perturbation
        self.gain_a = gain_a
        self.gain_c = gain_c
        self.alpha = alpha
        self.gamma = gamma
        self.iteration = 0

    def compute_gradient(
        self,
        circuit_builder: callable,
        params: NDArray[np.float64],
        observable: callable,
        backend: "AerSimulator",
    ) -> NDArray[np.float64]:
        """
        Compute SPSA gradient estimate.

        Args:
            circuit_builder: Function that builds circuit given parameters
            params: Current parameter values
            observable: Function that computes expectation from measurements
            backend: Quantum backend

        Returns:
            SPSA gradient estimate ∇̂θ⟨O⟩
        """
        n_params = len(params)

        # Generate random perturbation vector
        if self.perturbation is None:
            ck = self.gain_c / (self.iteration**self.gamma + 1)
            delta = np.random.choice([-1, 1], size=n_params).astype(np.float64)
        elif isinstance(self.perturbation, (int, float)):
            delta = np.random.choice([-1, 1], size=n_params).astype(np.float64) * self.perturbation
            ck = abs(self.perturbation)
        else:
            delta = np.random.choice([-1, 1], size=n_params).astype(np.float64) * np.array(
                self.perturbation
            )
            ck = np.linalg.norm(self.perturbation)

        # Create perturbed parameter vectors
        params_plus = params + ck * delta
        params_minus = params - ck * delta

        # Build and evaluate circuits
        circuit_plus = circuit_builder(params_plus)
        circuit_minus = circuit_builder(params_minus)

        exp_plus = observable(circuit_plus, backend)
        exp_minus = observable(circuit_minus, backend)

        # SPSA gradient estimate
        ak = self.gain_a / ((self.iteration + 1) ** self.alpha + 1)
        gradient = ak * (exp_plus - exp_minus) * delta / (2 * ck)

        self.iteration += 1

        return gradient


class FiniteDifferenceGradient(QuantumGradientEstimator):
    """
    Finite Difference gradient estimator.

    Approximates gradients using finite differences:
        ∂⟨O⟩/∂θᵢ ≈ (⟨O(θ + εeᵢ)⟩ - ⟨O(θ - εeᵢ)⟩) / 2ε

    Less accurate than parameter shift but simpler to implement.
    """

    def __init__(self, epsilon: float = 1e-3, method: str = "central"):
        """
        Initialize finite difference gradient.

        Args:
            epsilon: Step size for finite difference
            method: 'forward', 'backward', or 'central'
        """
        self.epsilon = epsilon
        self.method = method

    def compute_gradient(
        self,
        circuit_builder: callable,
        params: NDArray[np.float64],
        observable: callable,
        backend: "AerSimulator",
    ) -> NDArray[np.float64]:
        """
        Compute finite difference gradient.

        Args:
            circuit_builder: Function that builds circuit given parameters
            params: Current parameter values
            observable: Function that computes expectation from measurements
            backend: Quantum backend

        Returns:
            Finite difference gradient estimate
        """
        n_params = len(params)
        gradient = np.zeros(n_params, dtype=np.float64)

        base_circuit = circuit_builder(params)
        exp_base = observable(base_circuit, backend)

        for i in range(n_params):
            if self.method == "forward":
                params_perturbed = params.copy()
                params_perturbed[i] += self.epsilon
                circuit_perturbed = circuit_builder(params_perturbed)
                exp_perturbed = observable(circuit_perturbed, backend)

                gradient[i] = (exp_perturbed - exp_base) / self.epsilon

            elif self.method == "backward":
                params_perturbed = params.copy()
                params_perturbed[i] -= self.epsilon
                circuit_perturbed = circuit_builder(params_perturbed)
                exp_perturbed = observable(circuit_perturbed, backend)

                gradient[i] = (exp_base - exp_perturbed) / self.epsilon

            elif self.method == "central":
                params_plus = params.copy()
                params_plus[i] += self.epsilon
                circuit_plus = circuit_builder(params_plus)
                exp_plus = observable(circuit_plus, backend)

                params_minus = params.copy()
                params_minus[i] -= self.epsilon
                circuit_minus = circuit_builder(params_minus)
                exp_minus = observable(circuit_minus, backend)

                gradient[i] = (exp_plus - exp_minus) / (2 * self.epsilon)

        return gradient


@dataclass
class GradientConfig:
    """Configuration for quantum gradient computation."""

    method: str = "parameter_shift"  # parameter_shift, spsa, finite_difference
    shift: float = np.pi / 4
    epsilon: float = 1e-3
    spsa_gain_a: float = 1.0
    spsa_gain_c: float = 0.1
    batch_size: int = 4


class QuantumGradients:
    """
    Unified interface for quantum gradient computation.
    """

    def __init__(self, config: GradientConfig | None = None):
        """
        Initialize quantum gradient estimator.

        Args:
            config: Gradient configuration
        """
        self.config = config or GradientConfig()
        self.estimator = self._create_estimator()

    def _create_estimator(self) -> QuantumGradientEstimator:
        """Create gradient estimator from configuration."""
        if self.config.method == "parameter_shift":
            return ParameterShiftGradient(shift=self.config.shift)
        elif self.config.method == "spsa":
            return SPSAGradient(gain_a=self.config.spsa_gain_a, gain_c=self.config.spsa_gain_c)
        elif self.config.method == "finite_difference":
            return FiniteDifferenceGradient(epsilon=self.config.epsilon)
        else:
            raise ValueError(f"Unknown gradient method: {self.config.method}")

    def compute_gradient(
        self,
        circuit_builder: callable,
        params: NDArray[np.float64],
        observable: callable,
        backend: "AerSimulator",
    ) -> NDArray[np.float64]:
        """
        Compute gradient using configured method.

        Args:
            circuit_builder: Function QuantumCircuit(ndarray) -> QuantumCircuit
            params: Current parameter values
            observable: Function that takes circuit, backend and returns expectation
            backend: Quantum backend

        Returns:
            Gradient vector
        """
        return self.estimator.compute_gradient(circuit_builder, params, observable, backend)

    def update_estimator(self, config: GradientConfig) -> None:
        """
        Update gradient estimator with new configuration.

        Args:
            config: New gradient configuration
        """
        self.config = config
        self.estimator = self._create_estimator()


__all__ = [
    "QuantumGradientEstimator",
    "ParameterShiftGradient",
    "SPSAGradient",
    "FiniteDifferenceGradient",
    "GradientConfig",
    "QuantumGradients",
]
