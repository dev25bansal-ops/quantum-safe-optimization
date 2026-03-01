"""
Advanced Quantum Algorithms Module.

Provides implementations of:
- Quantum Fourier Transform (QFT)
- Quantum Phase Estimation (QPE)
- Variational Quantum Classifier (VQC)
- Quantum GAN (QGAN)
- Quantum Singular Value Transformation (QSVT)
"""

from __future__ import annotations

from collections.abc import Callable

import numpy as np
from numpy.typing import NDArray
from qiskit import QuantumCircuit
from qiskit.circuit import Parameter


class QuantumFourierTransform:
    """
    Quantum Fourier Transform implementation.

    QFT maps computational basis states to Fourier basis states:
    |j⟩ → 1/√N Σ_{k=0}^{N-1} ω^{jk} |k⟩ where ω = e^{2πi/N}

    Applications:
    - Phase estimation
    - Order finding
    - Hidden subgroup problems
    """

    @staticmethod
    def build_circuit(num_qubits: int, inverse: bool = False) -> QuantumCircuit:
        """
        Build a QFT quantum circuit.

        Args:
            num_qubits: Number of qubits (N = 2^n)
            inverse: If True, build inverse QFT

        Returns:
            QFT Quantum Circuit
        """
        qc = QuantumCircuit(num_qubits, name="IQFT" if inverse else "QFT")

        if inverse:
            qc = QuantumFourierTransform._build_inverse_qft(qc, num_qubits)
        else:
            qc = QuantumFourierTransform._build_qft(qc, num_qubits)

        return qc

    @staticmethod
    def _build_qft(qc: QuantumCircuit, num_qubits: int) -> QuantumCircuit:
        """Build forward QFT circuit."""
        for i in range(num_qubits):
            qc.h(i)
            for j in range(i + 1, num_qubits):
                angle = np.pi / (2 ** (j - i))
                qc.cp(angle, j, i)
            qc.h(i)

        qc = QuantumFourierTransform._reverse_qubit_order(qc, num_qubits)
        return qc

    @staticmethod
    def _build_inverse_qft(qc: QuantumCircuit, num_qubits: int) -> QuantumCircuit:
        """Build inverse QFT circuit."""
        qc = QuantumFourierTransform._reverse_qubit_order(qc, num_qubits)

        for i in range(num_qubits):
            qc.h(i)
            for j in range(i + 1, num_qubits):
                angle = -np.pi / (2 ** (j - i))
                qc.cp(angle, j, i)
            qc.h(i)

        return qc

    @staticmethod
    def _reverse_qubit_order(qc: QuantumCircuit, num_qubits: int) -> QuantumCircuit:
        """Reverse qubit order for in-place swaps."""
        for i in range(num_qubits // 2):
            qc.swap(i, num_qubits - 1 - i)
        return qc


class QuantumPhaseEstimation:
    """
    Quantum Phase Estimation algorithm.

    Estimates the phase φ of an eigenvalue λ = e^{2πiφ} of a unitary operator U.

    Precision: 2^n where n is number of precision qubits
    """

    def __init__(self, precision_qubits: int, unitary: Callable[[QuantumCircuit, int], None]):
        """
        Initialize QPE.

        Args:
            precision_qubits: Number of qubits for phase estimation (precision)
            unitary: Function that applies controlled-U gate given (circuit, target_qubit)
        """
        self.precision_qubits = precision_qubits
        self.unitary = unitary

    def build_circuit(
        self,
        num_state_qubits: int,
        initial_state: QuantumCircuit | None = None,
    ) -> QuantumCircuit:
        """
        Build QPE circuit.

        Args:
            num_state_qubits: Number of qubits in the state register
            initial_state: Optional initial state preparation circuit

        Returns:
            Complete QPE circuit
        """
        total_qubits = self.precision_qubits + num_state_qubits
        qc = QuantumCircuit(total_qubits, self.precision_qubits, name="QPEqc")

        # Apply Hadamard gates to precision qubits
        for i in range(self.precision_qubits):
            qc.h(i)

        # Prepare initial state if provided
        if initial_state:
            qc.compose(
                initial_state, qubits=range(self.precision_qubits, total_qubits), inplace=True
            )

        # Apply controlled-U^2^k gates
        for i in range(self.precision_qubits):
            num_applications = 2**i
            for _ in range(num_applications):
                self.unitary(qc, self.precision_qubits)

        # Apply inverse QFT
        qft_inv = QuantumFourierTransform.build_circuit(self.precision_qubits, inverse=True)
        qc.compose(qft_inv, qubits=range(self.precision_qubits), inplace=True)

        # Measure precision qubits
        qc.measure(range(self.precision_qubits), range(self.precision_qubits))

        return qc

    def estimate_phase(self, counts: dict[str, int]) -> float:
        """
        Estimate phase from measurement counts.

        Args:
            counts: Dictionary of measurement outcomes

        Returns:
            Estimated phase φ in [0, 1)
        """
        total_shots = sum(counts.values())

        # Compute weighted average
        phase_sum = 0.0
        for bitstring, count in counts.items():
            # Take only the first n bits (precision qubits)
            bits = bitstring[: self.precision_qubits]
            value = int(bits[::-1], 2)  # Reverse bit order for QPE convention
            phase = value / (2**self.precision_qubits)
            phase_sum += phase * count

        return phase_sum / total_shots


class VariationalQuantumClassifier:
    """
    Variational Quantum Classifier for machine learning tasks.

    Uses parameterized quantum circuits for classification where:
    - Feature map encodes classical data into quantum states
    - Variational ansatz produces decision boundaries
    - Measurement provides classification outputs
    """

    def __init__(
        self,
        num_qubits: int,
        num_classes: int = 2,
        feature_map_type: str = "zz",
        ansatz_type: str = "he",
        depth: int = 2,
    ):
        """
        Initialize VQC.

        Args:
            num_qubits: Number of qubits
            num_classes: Number of classification classes
            feature_map_type: Type of feature map ('zz', 'pauli', 'angle')
            ansatz_type: Type of variational ansatz ('he', 'chea', 'two_local')
            depth: Circuit depth (number of layers)
        """
        self.num_qubits = num_qubits
        self.num_classes = num_classes
        self.feature_map_type = feature_map_type
        self.ansatz_type = ansatz_type
        self.depth = depth

        self._feature_params: list[Parameter] = []
        self._variational_params: list[Parameter] = []

    def build_feature_map(self, features: NDArray[np.float64]) -> QuantumCircuit:
        """
        Build feature map circuit to encode classical data.

        Args:
            features: Input features of shape (num_features,)

        Returns:
            Feature map circuit
        """
        qc = QuantumCircuit(self.num_qubits, name="FeatureMap")

        if self.feature_map_type == "zz":
            qc = self._zz_feature_map(qc, features)
        elif self.feature_map_type == "pauli":
            qc = self._pauli_feature_map(qc, features)
        elif self.feature_map_type == "angle":
            qc = self._angle_feature_map(qc, features)

        return qc

    def _zz_feature_map(
        self,
        qc: QuantumCircuit,
        features: NDArray[np.float64],
    ) -> QuantumCircuit:
        """ZZ feature map with entanglement."""
        n = self.num_qubits

        # Apply initial Hadamard
        for i in range(n):
            qc.h(i)

        # Apply ZZ rotations with features
        for i in range(n):
            idx = i % len(features)
            qc.rz(2 * features[idx], i)

        # Apply entanglement (ZZ gates)
        for i in range(n - 1):
            for j in range(i + 1, n):
                qc.cx(i, j)
                qc.rz(
                    2 * features[(i + j) % len(features)] * features[idx]
                    if i + j < len(features)
                    else 0,
                    j,
                )
                qc.cx(i, j)

        return qc

    def _pauli_feature_map(
        self,
        qc: QuantumCircuit,
        features: NDArray[np.float64],
    ) -> QuantumCircuit:
        """Pauli feature map."""
        for i in range(self.num_qubits):
            for _ in range(self.depth):
                idx = i % len(features)
                qc.h(i)
                qc.rz(features[idx], i)
                qc.rx(features[idx + 1] if idx + 1 < len(features) else 0, i)

        return qc

    def _angle_feature_map(
        self,
        qc: QuantumCircuit,
        features: NDArray[np.float64],
    ) -> QuantumCircuit:
        """Angle feature map."""
        for i in range(self.num_qubits):
            idx = i % len(features)
            qc.ry(features[idx], i)

        return qc

    def build_ansatz(self) -> QuantumCircuit:
        """
        Build variational ansatz with trainable parameters.

        Returns:
            Parameterized ansatz circuit
        """
        qc = QuantumCircuit(self.num_qubits, name="Ansatz")

        if self.ansatz_type == "he":
            qc = self._hardware_efficient_ansatz(qc)
        elif self.ansatz_type == "chea":
            qc = self._chebyshev_hardware_efficient_ansatz(qc)
        elif self.ansatz_type == "two_local":
            qc = self._two_local_ansatz(qc)

        return qc

    def _hardware_efficient_ansatz(self, qc: QuantumCircuit) -> QuantumCircuit:
        """Hardware Efficient Ansatz with single-qubit rotations and entanglement."""
        self._variational_params = []

        for d in range(self.depth):
            # Single-qubit rotations
            for i in range(self.num_qubits):
                theta_rz = Parameter(f"θ_rz_{d}_{i}")
                theta_ry = Parameter(f"θ_ry_{d}_{i}")
                self._variational_params.extend([theta_rz, theta_ry])

                qc.rz(theta_rz, i)
                qc.ry(theta_ry, i)

            # Entanglement layer
            for i in range(self.num_qubits - 1):
                qc.cx(i, i + 1)

        return qc

    def _chebyshev_hardware_efficient_ansatz(self, qc: QuantumCircuit) -> QuantumCircuit:
        """CHEA: Chebyshev-Hardware-Efficient Ansatz."""
        self._variational_params = []

        for d in range(self.depth):
            for i in range(self.num_qubits):
                theta = Parameter(f"θ_{d}_{i}")
                self._variational_params.append(theta)
                qc.ry(theta, i)

            for i in range(self.num_qubits - 1):
                qc.cx(i, i + 1)

        return qc

    def _two_local_ansatz(self, qc: QuantumCircuit) -> QuantumCircuit:
        """Two-local ansatz pattern."""
        self._variational_params = []

        for d in range(self.depth):
            # Rotation blocks
            for i in range(self.num_qubits):
                theta3 = Parameter(f"θ3_{d}_{i}")
                theta2 = Parameter(f"θ2_{d}_{i}")
                theta1 = Parameter(f"θ1_{d}_{i}")
                self._variational_params.extend([theta1, theta2, theta3])

                qc.rz(theta1, i)
                qc.ry(theta2, i)
                qc.rz(theta3, i)

            # Entanglement
            for i in range(self.num_qubits):
                for j in range(i + 1, min(i + 3, self.num_qubits)):
                    qc.cx(i, j)

        return qc

    def get_num_parameters(self) -> int:
        """Get total number of trainable parameters."""
        return len(self._variational_params)

    def bind_parameters(self, qc: QuantumCircuit, params: NDArray[np.float64]) -> QuantumCircuit:
        """
        Bind parameter values to the circuit.

        Args:
            qc: Parameterized circuit
            params: Parameter values

        Returns:
            Circuit with bound parameters
        """
        param_dict = {p: float(v) for p, v in zip(self._variational_params, params, strict=False)}
        return qc.assign_parameters(param_dict)


class QuantumGAN:
    """
    Quantum Generative Adversarial Network.

    Uses quantum circuits for both generator and discriminator:
    - Generator: VQC that produces quantum states from latent vectors
    - Discriminator: VQC that classifies real vs generated samples
    """

    def __init__(
        self,
        latent_dim: int,
        data_dim: int,
        num_qubits_generator: int,
        num_qubits_discriminator: int,
    ):
        """
        Initialize QGAN.

        Args:
            latent_dim: Dimension of latent space
            data_dim: Dimension of output data space
            num_qubits_generator: Number of qubits in generator circuit
            num_qubits_discriminator: Number of qubits in discriminator circuit
        """
        self.latent_dim = latent_dim
        self.data_dim = data_dim
        self.num_qubits_generator = num_qubits_generator
        self.num_qubits_discriminator = num_qubits_discriminator

        self.generator_params: list[Parameter] = []
        self.discriminator_params: list[Parameter] = []

    def build_generator(self, latent_vector: NDArray[np.float64], depth: int = 2) -> QuantumCircuit:
        """
        Build generator quantum circuit.

        Args:
            latent_vector: Latent vector input
            depth: Circuit depth

        Returns:
            Generator circuit
        """
        qc = QuantumCircuit(self.num_qubits_generator, name="Generator")

        # Encode latent vector
        for i in range(min(self.num_qubits_generator, len(latent_vector))):
            qc.ry(latent_vector[i], i)

        # Variational layers
        self.generator_params = []
        for d in range(depth):
            for i in range(self.num_qubits_generator):
                theta = Parameter(f"gen_θ_{d}_{i}")
                self.generator_params.append(theta)
                qc.ry(theta, i)

                phi = Parameter(f"gen_φ_{d}_{i}")
                self.generator_params.append(phi)
                qc.rz(phi, i)

            # Entanglement
            for i in range(self.num_qubits_generator - 1):
                qc.cx(i, i + 1)

        return qc

    def build_discriminator(
        self, data_sample: NDArray[np.float64], depth: int = 2
    ) -> QuantumCircuit:
        """
        Build discriminator quantum circuit.

        Args:
            data_sample: Input data sample
            depth: Circuit depth

        Returns:
            Discriminator circuit
        """
        qc = QuantumCircuit(self.num_qubits_discriminator, 1, name="Discriminator")

        # Encode data sample
        for i in range(min(self.num_qubits_discriminator, len(data_sample))):
            angle = data_sample[i] * np.pi
            qc.ry(angle, i)

        # Variational layers
        self.discriminator_params = []
        for d in range(depth):
            for i in range(self.num_qubits_discriminator):
                theta = Parameter(f"disc_θ_{d}_{i}")
                self.discriminator_params.append(theta)
                qc.ry(theta, i)

            # Entanglement
            for i in range(self.num_qubits_discriminator - 1):
                qc.cx(i, i + 1)

        # Output measurement
        qc.measure(0, 0)

        return qc

    def get_generator_loss(
        self,
        fake_counts: dict[str, int],
        disc_output_fake: float,
    ) -> float:
        """
        Compute generator loss.

        Args:
            fake_counts: Counts from generator circuit
            disc_output_fake: Discriminator output for fake samples

        Returns:
            Generator loss value
        """
        # Binary cross-entropy loss: maximize discriminator error on fake samples
        loss = -np.log(disc_output_fake + 1e-10)
        return loss

    def get_discriminator_loss(
        self,
        disc_output_real: float,
        disc_output_fake: float,
    ) -> float:
        """
        Compute discriminator loss.

        Args:
            disc_output_real: Discriminator output for real samples
            disc_output_fake: Discriminator output for fake samples

        Returns:
            Discriminator loss value
        """
        # Binary cross-entropy loss
        loss_real = -np.log(disc_output_real + 1e-10)
        loss_fake = -np.log(1 - disc_output_fake + 1e-10)
        return loss_real + loss_fake


class QuantumSingularValueTransformation:
    """
    Quantum Singular Value Transformation (QSVT).

    General framework for quantum algorithms using polynomial transformations
    of singular values including:
    - Quantum linear systems
    - Quantum eigenvalue amplification
    - Quantum amplitude amplification
    """

    def __init__(self, num_qubits: int, degree: int):
        """
        Initialize QSVT.

        Args:
            num_qubits: Number of qubits in the block encoding
            degree: Degree of approximating polynomial
        """
        self.num_qubits = num_qubits
        self.degree = degree

    def build_qsvt_circuit(
        self,
        block_encoding: QuantumCircuit,
        phi_sequence: NDArray[np.float64],
    ) -> QuantumCircuit:
        """
        Build QSVT circuit from polynomial phase sequence.

        Args:
            block_encoding: Circuit that implements the block encoding
            phi_sequence: Sequence of phase angles [φ_0, φ_1, ..., φ_d]

        Returns:
            QSVT circuit
        """
        total_qubits = self.num_qubits + 1  # Add ancilla qubit
        qc = QuantumCircuit(total_qubits, name="QSVTqst")

        # Initialize ancilla in equal superposition
        qc.h(0)

        # Apply QSVT sequence
        for _i, phi in enumerate(phi_sequence):
            # Controlled block encoding
            qc.compose(block_encoding, qubits=range(1, total_qubits), control=0, inplace=True)

            # Phase rotation on ancilla
            qc.rz(2 * phi, 0)

        return qc

    @staticmethod
    def phase_sequence_from_polynomial(
        coefficients: NDArray[np.float64],
        degree: int,
    ) -> NDArray[np.float64]:
        """
        Generate phase sequence from polynomial coefficients using Chebyshev expansion.

        Args:
            coefficients: Polynomial coefficients
            degree: Degree of polynomial

        Returns:
            Sequence of phase angles
        """
        # Simplified: use linear interpolation from coefficients
        # In practice, this would use quantum signal processing techniques
        num_phases = degree + 1
        bases = np.linspace(0, 1, num_phases)

        phases = []
        for i in range(num_phases):
            phase = np.pi * (
                coefficients @ np.array([bases[i] ** j for j in range(len(coefficients))])
            )
            phases.append(phase)

        return np.array(phases)

    def quantum_amplitude_amplification(self, success_probability: float) -> QuantumCircuit:
        """
        Build amplitude amplification circuit (a special case of QSVT).

        Args:
            success_probability: Initial probability of success

        Returns:
            Amplitude amplification circuit
        """
        # Number of iterations
        num_iterations = int(np.pi / (4 * np.arcsin(np.sqrt(success_probability))))

        # For A², the phase sequence is constant
        phi_sequence = np.full(num_iterations * 2, 0)

        # Build placeholder block encoding (would be problem-specific)
        block_encoding = QuantumCircuit(self.num_qubits, name="BlockEnc")

        return self.build_qsvt_circuit(block_encoding, phi_sequence)


__all__ = [
    "QuantumFourierTransform",
    "QuantumPhaseEstimation",
    "VariationalQuantumClassifier",
    "QuantumGAN",
    "QuantumSingularValueTransformation",
]
