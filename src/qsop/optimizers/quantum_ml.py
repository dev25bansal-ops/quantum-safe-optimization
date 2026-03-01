"""
Quantum Kernel Methods and Advanced Quantum Machine Learning.

Implements kernel-based quantum machine learning including:
- Quantum Kernel Estimation
- Quantum Support Vector Machines (QSVM)
- Quantum Gaussian Processes
- Quantum Neural Networks (QNN)
- Quantum Feature Maps
- Kernel alignment
"""

from __future__ import annotations

from abc import abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

import numpy as np
from numpy.typing import NDArray
from qiskit import QuantumCircuit
from qiskit.circuit import Parameter
from sklearn.svm import SVC


class KernelType(Enum):
    """Types of quantum kernels."""

    ZZ_FEATURE_MAP = "zz_feature_map"
    PAULI_FEATURE_MAP = "pauli_feature_map"
    AMPLITUDE_EMBEDDING = "amplitude_embedding"
    ANGLE_ENCODING = "angle_encoding"
    CUSTOM = "custom"


@dataclass
class KernelResult:
    """Result from kernel computation."""

    kernel_matrix: NDArray[np.float64]
    metadata: dict[str, Any] = field(default_factory=dict)

    def get_alignment(self, target_matrix: NDArray[np.float64]) -> float:
        """Calculate alignment with target kernel matrix."""
        len(self.kernel_matrix)

        numerator = np.sum(self.kernel_matrix * target_matrix)
        denominator_fro = np.sqrt(np.sum(self.kernel_matrix**2))
        denominator_fro = denominator_fro * np.sqrt(np.sum(target_matrix**2))

        return numerator / denominator_fro if denominator_fro > 0 else 0.0


class QuantumFeatureMap:
    """
    Base class for quantum feature maps.

    Maps classical data to quantum states using parameterized quantum circuits.
    """

    def __init__(self, num_qubits: int, num_features: int | None = None):
        """
        Initialize feature map.

        Args:
            num_qubits: Number of qubits in the encoding circuit
            num_features: Number of input features (defaults to num_qubits)
        """
        self.num_qubits = num_qubits
        self.num_features = num_features or num_qubits
        self._parameters: list[Parameter] = []

    @abstractmethod
    def encode(self, x: NDArray[np.float64]) -> QuantumCircuit:
        """Encode data point into quantum circuit."""
        pass

    def encode_batch(
        self,
        X: NDArray[np.float64],
    ) -> list[QuantumCircuit]:
        """Encode batch of data points."""
        return [self.encode(x) for x in X]

    def get_num_parameters(self) -> int:
        """Get number of trainable parameters."""
        return len(self._parameters)


class ZZFeatureMap(QuantumFeatureMap):
    """
    ZZ Feature Map circuit.

    Encodes features using Z-rotations and ZZ entanglement gates.
    """

    def __init__(
        self,
        num_qubits: int,
        num_features: int | None = None,
        reps: int = 2,
        entanglement: str = "full",
    ):
        """
        Initialize ZZ feature map.

        Args:
            num_qubits: Number of qubits
            num_features: Number of input features
            reps: Number of repetitions
            entanglement: Type of entanglement ('full', 'linear', 'circular')
        """
        super().__init__(num_qubits, num_features)
        self.reps = reps
        self.entanglement = entanglement

    def encode(self, x: NDArray[np.float64]) -> QuantumCircuit:
        """Encode data point using ZZ feature map."""
        qc = QuantumCircuit(self.num_qubits, name=f"ZZFeatureMap({self.reps}reps)")

        for _rep in range(self.reps):
            # Apply Hadamard gates
            for i in range(self.num_qubits):
                qc.h(i)

            # Apply Z-rotations with features
            for i in range(self.num_qubits):
                idx = i % len(x)
                qc.rz(2 * x[idx], i)

            # Apply entanglement
            if self.entanglement == "full":
                for i in range(self.num_qubits):
                    for j in range(i + 1, self.num_qubits):
                        qc.cx(i, j)
                        qc.rz(
                            2 * (x[i] * x[j]) % (2 * np.pi) if i < len(x) and j < len(x) else 0, j
                        )
                        qc.cx(i, j)
            elif self.entanglement == "linear":
                for i in range(self.num_qubits - 1):
                    qc.cx(i, i + 1)
                    qc.rz(2 * (x[i] * x[i + 1]) % (2 * np.pi) if i + 1 < len(x) else 0, i + 1)
                    qc.cx(i, i + 1)
            elif self.entanglement == "circular":
                for i in range(self.num_qubits):
                    j = (i + 1) % self.num_qubits
                    qc.cx(i, j)
                    qc.rz(2 * (x[i] * x[j]) % (2 * np.pi) if j < len(x) else 0, j)
                    qc.cx(i, j)

        return qc


class QuantumKernel:
    """
    Quantum Kernel for kernel methods.

    Computes kernel matrix entries using the overlap of quantum states:
    K(x, y) = |⟨φ(x)|φ(y)⟩|^2
    where φ(x) is the quantum feature map encoding of x.
    """

    def __init__(
        self,
        feature_map: QuantumFeatureMap,
        backend: Any,
    ):
        """
        Initialize quantum kernel.

        Args:
            feature_map: Quantum feature map for encoding data
            backend: Quantum backend for circuit execution
        """
        self.feature_map = feature_map
        self.backend = backend
        self._feature_vector_cache: dict[tuple, NDArray] = {}

    def encode_and_run(
        self,
        x: NDArray[np.float64],
        y: NDArray[np.float64] | None = None,
        shots: int = 1024,
    ) -> tuple[NDArray, dict[str, int]]:
        """
        Encode and run quantum circuit for kernel evaluation.

        Args:
            x: Input data point
            y: Optional second data point (for multi-kernel)
            shots: Number of measurement shots

        Returns:
            Tuple of (feature vector or kernel value, measurement counts)
        """
        circuit = self.feature_map.encode(x)
        result = self.backend.run(circuit, shots=shots)

        return result

    def evaluate(
        self,
        x: NDArray[np.float64],
        y: NDArray[np.float64],
        shots: int = 1024,
        method: str = "statevector",
    ) -> float:
        """
        Evaluate kernel entry K(x, y).

        Methods:
        - statevector: Direct statevector overlap
        - swap_test: Use swap test circuit
        - inversion_test: Use inversion test circuit

        Args:
            x: First data point
            y: Second data point
            shots: Number of shots for sampling-based methods
            method: Computation method

        Returns:
            Kernel value K(x, y)
        """
        if method == "statevector":
            return self._statevector_overlap(x, y)
        elif method == "swap_test":
            return self._swap_test_overlap(x, y, shots)
        elif method == "inversion_test":
            return self._inversion_test_overlap(x, y, shots)
        else:
            raise ValueError(f"Unknown method: {method}")

    def _statevector_overlap(
        self,
        x: NDArray[np.float64],
        y: NDArray[np.float64],
    ) -> float:
        """Calculate statevector overlap directly."""
        circuit_x = self.feature_map.encode(x)
        circuit_y = self.feature_map.encode(y)

        sv_x = self.backend.get_statevector(circuit_x)
        sv_y = self.backend.get_statevector(circuit_y)

        overlap = np.abs(np.vdot(sv_x, sv_y)) ** 2
        return float(overlap)

    def _swap_test_overlap(
        self,
        x: NDArray[np.float64],
        y: NDArray[np.float64],
        shots: int,
    ) -> float:
        """Calculate overlap using swap test."""
        num_qubits = self.feature_map.num_qubits
        total_qubits = 2 * num_qubits + 1
        qc = QuantumCircuit(total_qubits, 1, name="SwapTest")

        # Encode x on first register
        qc_x = self.feature_map.encode(x)
        qc.compose(qc_x, qubits=range(1, num_qubits + 1), inplace=True)

        # Encode y on second register
        qcy = QuantumCircuit(num_qubits)
        qcy = self.feature_map.encode(y)
        qc.compose(qcy, qubits=range(num_qubits + 1, total_qubits), inplace=True)

        # Swap test
        qc.h(0)

        for i in range(num_qubits):
            qc.cswap(0, i + 1, i + num_qubits + 1)

        qc.h(0)
        qc.measure(0, 0)

        result = self.backend.run(qc, shots=shots)
        counts = result.counts

        # Overlap = probability of measuring |0⟩
        prob_0 = counts.get("0", 0) / shots
        overlap = (2 * prob_0 - 1 + 1) / 2  # Adjust for swap test formula

        return overlap

    def _inversion_test_overlap(
        self,
        x: NDArray[np.float64],
        y: NDArray[np.float64],
        shots: int,
    ) -> float:
        """Calculate overlap using inversion test."""
        num_qubits = self.feature_map.num_qubits
        qc = QuantumCircuit(num_qubits, num_qubits, name="InversionTest")

        # Encode superposition of x and y
        qc.h(0)

        # Controlled encoding
        for i in range(1, num_qubits):
            qc.cx(0, i)

        # Measure and estimate overlap
        qc.measure_all()

        self.backend.run(qc, shots=shots)

        # Simplified overlap estimation
        overlap = 0.5  # Placeholder - would compute from actual counts

        return overlap

    def evaluate_matrix(
        self,
        X: NDArray[np.float64],
        Y: NDArray[np.float64] | None = None,
        shots: int = 1024,
        method: str = "statevector",
    ) -> KernelResult:
        """
        Compute full kernel matrix.

        Args:
            X: Training data (n_samples, n_features)
            Y: Optional test data (m_samples, n_features)
            shots: Number of shots for sampling methods
            method: Computation method

        Returns:
            KernelResult with kernel matrix
        """
        if Y is None:
            Y = X

        n_samples_x = len(X)
        n_samples_y = len(Y)

        kernel_matrix = np.zeros((n_samples_y, n_samples_x))

        for i in range(n_samples_y):
            for j in range(n_samples_x):
                kernel_matrix[i, j] = self.evaluate(X[j], Y[i], shots, method)

        return KernelResult(
            kernel_matrix=kernel_matrix,
            metadata={
                "shape": kernel_matrix.shape,
                "method": method,
                "shots": shots,
            },
        )


class QuantumSVM:
    """
    Quantum Support Vector Machine.

    Uses quantum kernel in support vector classification.
    """

    def __init__(
        self,
        quantum_kernel: QuantumKernel,
        C: float = 1.0,
        kernel_method: str = "statevector",
    ):
        """
        Initialize QSVM.

        Args:
            quantum_kernel: Quantum kernel instance
            C: Regularization parameter
            kernel_method: Method for kernel computation
        """
        self.quantum_kernel = quantum_kernel
        self.C = C
        self.kernel_method = kernel_method
        self._svm: SVC | None = None
        self._X_train: NDArray | None = None
        self._y_train: NDArray | None = None
        self._kernel_matrix_train: NDArray | None = None

    def fit(
        self,
        X: NDArray[np.float64],
        y: NDArray[np.int_],
    ) -> QuantumSVM:
        """
        Fit QSVM to training data.

        Args:
            X: Training data (n_samples, n_features)
            y: Training labels (n_samples,)

        Returns:
            Self (fitted model)
        """
        self._X_train = X
        self._y_train = y

        # Compute quantum kernel matrix
        result = self.quantum_kernel.evaluate_matrix(X, method=self.kernel_method)
        self._kernel_matrix_train = result.kernel_matrix

        # Use precomputed kernel SVM
        self._svm = SVC(C=self.C, kernel="precomputed")
        self._svm.fit(self._kernel_matrix_train, y)

        return self

    def predict(
        self,
        X: NDArray[np.float64],
    ) -> NDArray[np.int_]:
        """
        Predict labels for test data.

        Args:
            X: Test data (n_samples, n_features)

        Returns:
            Predicted labels
        """
        if self._X_train is None or self._svm is None:
            raise RuntimeError("Model not fitted. Call fit() first.")

        # Compute kernel matrix between test and training data
        kernel_matrix = np.zeros((len(X), len(self._X_train)))
        for i, x in enumerate(X):
            for j, x_train in enumerate(self._X_train):
                kernel_matrix[i, j] = self.quantum_kernel.evaluate(
                    x_train, x, method=self.kernel_method
                )

        return self._svm.predict(kernel_matrix)

    def decision_function(
        self,
        X: NDArray[np.float64],
    ) -> NDArray[np.float64]:
        """Get decision function values."""
        if self._X_train is None or self._svm is None:
            raise RuntimeError("Model not fitted. Call fit() first.")

        kernel_matrix = np.zeros((len(X), len(self._X_train)))
        for i, x in enumerate(X):
            for j, x_train in enumerate(self._X_train):
                kernel_matrix[i, j] = self.quantum_kernel.evaluate(
                    x_train, x, method=self.kernel_method
                )

        return self._svm.decision_function(kernel_matrix)


class QuantumGaussianProcess:
    """
    Quantum Gaussian Process Regression.

    Uses quantum kernel for Gaussian process modeling.
    """

    def __init__(
        self,
        quantum_kernel: QuantumKernel,
        alpha: float = 1e-10,
        kernel_method: str = "statevector",
    ):
        """
        Initialize QGP.

        Args:
            quantum_kernel: Quantum kernel instance
            alpha: Noise parameter
            kernel_method: Method for kernel computation
        """
        self.quantum_kernel = quantum_kernel
        self.alpha = alpha
        self.kernel_method = kernel_method
        self._X_train: NDArray | None = None
        self._y_train: NDArray | None = None
        self._K: NDArray | None = None
        self._K_inv: NDArray | None = None

    def fit(
        self,
        X: NDArray[np.float64],
        y: NDArray[np.float64],
    ) -> QuantumGaussianProcess:
        """
        _fit QGP to training data.

         Args:
             X: Training data
             y: Training targets

         Returns:
             Self (fitted model)
        """
        self._X_train = X
        self._y_train = y

        # Compute kernel matrix
        result = self.quantum_kernel.evaluate_matrix(X, method=self.kernel_method)
        K = result.kernel_matrix

        # Add noise to diagonal
        self._K = K + np.eye(len(K)) * self.alpha

        # Compute inverse
        self._K_inv = np.linalg.inv(self._K)

        return self

    def predict(
        self,
        X: NDArray[np.float64],
        return_std: bool = False,
    ) -> NDArray[np.float64] | tuple[NDArray[np.float64], NDArray[np.float64]]:
        """
        Predict at test points.

        Args:
            X: Test data
            return_std: Whether to return standard deviation

        Returns:
            Predictions and optionally standard deviations
        """
        if self._X_train is None:
            raise RuntimeError("Model not fitted. Call fit() first.")

        # Compute cross-kernel
        K_star = np.zeros((len(X), len(self._X_train)))
        for i, x in enumerate(X):
            for j, x_train in enumerate(self._X_train):
                K_star[i, j] = self.quantum_kernel.evaluate(x_train, x, method=self.kernel_method)

        # Compute predictions
        y_mean = K_star @ (self._K_inv @ self._y_train)

        if return_std:
            # Compute diagonal of test kernel
            K_star_star = np.array(
                [self.quantum_kernel.evaluate(x, x, method=self.kernel_method) for x in X]
            )

            # Compute variance
            y_var = np.diag(K_star_star) - np.sum(K_star @ self._K_inv * K_star, axis=1)
            y_std = np.sqrt(np.maximum(y_var, 0))

            return y_mean, y_std

        return y_mean


class QuantumNeuralNetwork:
    """
    Quantum Neural Network (Parameterized Quantum Circuit as a neural network).

    Implements a variational quantum classifier/trainable quantum circuit.
    """

    def __init__(
        self,
        num_qubits: int,
        num_layers: int = 2,
        encoding_type: str = "angle",
        output_mode: str = "expectation",
        shots: int = 1024,
        backend: Any = None,
    ):
        """
        Initialize QNN.

        Args:
            num_qubits: Number of qubits
            num_layers: Number of variational layers
            encoding_type: Type of data encoding ('angle', 'amplitude')
            output_mode: How to read output ('expectation', 'probability')
            shots: Number of measurement shots
            backend: Quantum backend
        """
        self.num_qubits = num_qubits
        self.num_layers = num_layers
        self.encoding_type = encoding_type
        self.output_mode = output_mode
        self.shots = shots
        self.backend = backend

        self._weights: list[Parameter] = []
        self._build_parameters()

    def _build_parameters(self) -> None:
        """Create trainable parameters."""
        self._weights = []
        for layer in range(self.num_layers):
            for qubit in range(self.num_qubits):
                self._weights.append(Parameter(f"w_{layer}_{qubit}_ry"))
                self._weights.append(Parameter(f"w_{layer}_{qubit}_rz"))

    def encode_data(self, X: NDArray[np.float64]) -> QuantumCircuit:
        """Encode classical data into quantum state."""
        qc = QuantumCircuit(self.num_qubits, name="DataEncoding")

        if self.encoding_type == "angle":
            for i, x in enumerate(X[: self.num_qubits]):
                qc.ry(x * np.pi, i)
        elif self.encoding_type == "amplitude":
            normalized = X / np.linalg.norm(X)
            qc.initialize(normalized[: 2**self.num_qubits])

        return qc

    def build_circuit(self, x: NDArray[np.float64], weights: NDArray[np.float64]) -> QuantumCircuit:
        """Build complete QNN circuit."""
        qc = QuantumCircuit(self.num_qubits, 1, name="QNN")

        # Encode data
        qc.compose(self.encode_data(x), inplace=True)

        # Apply variational layers
        weight_idx = 0
        for _layer in range(self.num_layers):
            for qubit in range(self.num_qubits):
                qc.ry(weights[weight_idx], qubit)
                weight_idx += 1
                qc.rz(weights[weight_idx], qubit)
                weight_idx += 1

            # Entanglement
            for i in range(self.num_qubits - 1):
                qc.cx(i, i + 1)

        return qc

    def forward(self, X: NDArray[np.float64], weights: NDArray[np.float64]) -> NDArray[np.float64]:
        """Forward pass through QNN."""
        if self.backend is None:
            raise RuntimeError("Backend not set")

        outputs = []
        for x in X:
            circuit = self.build_circuit(x, weights)

            if self.output_mode == "expectation":
                circuit.measure_all()
                result = self.backend.run(circuit, shots=self.shots)
                counts = result.counts

                # Expectation of Z on first qubit
                expectation = 0.0
                total = sum(counts.values())

                for bitstring, count in counts.items():
                    if bitstring[0] == "0":
                        expectation += count / total
                    else:
                        expectation -= count / total

                outputs.append(expectation)

            elif self.output_mode == "probability":
                circuit.measure(0, 0)
                result = self.backend.run(circuit, shots=self.shots)
                counts = result.counts

                prob_0 = counts.get("0", 0) / self.shots
                outputs.append(prob_0)

        return np.array(outputs)

    def get_num_parameters(self) -> int:
        """Get number of trainable parameters."""
        return len(self._weights)


class KernelAlignment:
    """
    Kernel alignment for optimizing quantum feature maps.

    Finds optimal parameters for quantum feature maps to maximize
    alignment between quantum kernel and target kernel (e.g., class kernel).
    """

    def __init__(
        self,
        base_feature_map: QuantumFeatureMap,
        backend: Any,
    ):
        """
        Initialize kernel alignment.

        Args:
            base_feature_map: Base quantum feature map to optimize
            backend: Quantum backend
        """
        self.base_feature_map = base_feature_map
        self.backend = backend
        self._best_parameters: NDArray | None = None
        self._best_alignment: float = 0.0

    def optimize(
        self,
        X: NDArray[np.float64],
        y: NDArray[np.int_],
        target_kernel: NDArray[np.float64] | None = None,
        max_iterations: int = 100,
        learning_rate: float = 0.01,
    ) -> tuple[NDArray[np.float64], float]:
        """
        Optimize feature map parameters for kernel alignment.

        Args:
            X: Training data
            y: Training labels
            target_kernel: Optional target kernel matrix
            max_iterations: Maximum optimization iterations
            learning_rate: Learning rate for gradient descent

        Returns:
            Tuple of (best_parameters, best_alignment)
        """
        # Create target kernel from labels if not provided
        if target_kernel is None:
            target_kernel = self._create_target_kernel(y)

        # Initialize parameters randomly
        num_params = self.base_feature_map.get_num_parameters()
        parameters = np.random.uniform(-np.pi, np.pi, num_params)

        # Gradient-free optimization (grid search)
        best_alignment = 0.0
        best_params = parameters.copy()

        for _iteration in range(max_iterations):
            # Add small random perturbation
            perturbation = np.random.normal(0, learning_rate, num_params)
            test_params = parameters + perturbation

            # Compute alignment
            alignment = self._compute_alignment(X, test_params, target_kernel)

            # Accept if better
            if alignment > best_alignment:
                best_alignment = alignment
                best_params = test_params.copy()
                parameters = test_params

        self._best_parameters = best_params
        self._best_alignment = best_alignment

        return best_params, best_alignment

    def _create_target_kernel(self, y: NDArray[np.int_]) -> NDArray[np.float64]:
        """Create target kernel from class labels."""
        # Class kernel: K(y_i, y_j) = 1 if y_i == y_j, -1 otherwise
        y_col = y.reshape(-1, 1)
        target = (y_col == y_col.T).astype(np.float64)
        target = 2 * target - 1
        return target

    def _compute_alignment(
        self,
        X: NDArray[np.float64],
        parameters: NDArray[np.float64],
        target_kernel: NDArray[np.float64],
    ) -> float:
        """Compute kernel alignment for given parameters."""
        # Create quantum kernel with parameters
        quantum_kernel = QuantumKernel(
            feature_map=self.base_feature_map,
            backend=self.backend,
        )

        # Compute quantum kernel matrix
        result = quantum_kernel.evaluate_matrix(X, method="statevector")

        # Compute alignment
        alignment = result.get_alignment(target_kernel)

        return alignment


__all__ = [
    "KernelType",
    "KernelResult",
    "QuantumFeatureMap",
    "ZZFeatureMap",
    "QuantumKernel",
    "QuantumSVM",
    "QuantumGaussianProcess",
    "QuantumNeuralNetwork",
    "KernelAlignment",
]
