"""
Quantum Key Distribution (QKD) Simulation.

Simulates BB84, E91, and other QKD protocols for educational and testing purposes.
"""

import hashlib
import json
import random
import secrets
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Optional
from uuid import uuid4

import structlog

logger = structlog.get_logger()


class QKDProtocol(str, Enum):
    BB84 = "bb84"
    E91 = "e91"
    B92 = "b92"
    SARG04 = "sarg04"


class Basis(str, Enum):
    RECTILINEAR = "+"  # |0>, |1>
    DIAGONAL = "x"  # |+>, |->
    CIRCULAR = "o"  # |R>, |L>


@dataclass
class QubitState:
    value: int  # 0 or 1
    basis: Basis
    photon_number: int = 1

    def encode(self) -> str:
        return f"{self.value}{self.basis.value}{self.photon_number}"


@dataclass
class QKDSimulationResult:
    simulation_id: str
    protocol: QKDProtocol
    alice_key: str
    bob_key: str
    sifted_key_length: int
    error_rate: float
    secure_key_length: int
    eavesdropper_detected: bool
    quantum_channel_losses: float
    classical_channel_uses: int
    duration_ms: float
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> dict:
        return {
            "simulation_id": self.simulation_id,
            "protocol": self.protocol.value,
            "alice_key": self.alice_key,
            "bob_key": self.bob_key,
            "sifted_key_length": self.sifted_key_length,
            "error_rate": self.error_rate,
            "secure_key_length": self.secure_key_length,
            "eavesdropper_detected": self.eavesdropper_detected,
            "quantum_channel_losses": self.quantum_channel_losses,
            "classical_channel_uses": self.classical_channel_uses,
            "duration_ms": self.duration_ms,
            "created_at": self.created_at.isoformat(),
        }


class BB84Simulator:
    """Simulates the BB84 quantum key distribution protocol."""

    def __init__(
        self,
        key_length: int = 256,
        error_threshold: float = 0.11,  # QBER threshold
        channel_loss_rate: float = 0.05,
        eavesdropper_rate: float = 0.0,
    ):
        self.key_length = key_length
        self.error_threshold = error_threshold
        self.channel_loss_rate = channel_loss_rate
        self.eavesdropper_rate = eavesdropper_rate

    def generate_random_bits(self, n: int) -> list[int]:
        """Generate n random bits."""
        return [secrets.randbelow(2) for _ in range(n)]

    def generate_random_bases(self, n: int) -> list[Basis]:
        """Generate n random bases."""
        bases = [Basis.RECTILINEAR, Basis.DIAGONAL]
        return [random.choice(bases) for _ in range(n)]

    def encode_bit(self, bit: int, basis: Basis) -> QubitState:
        """Encode a bit in the specified basis."""
        return QubitState(value=bit, basis=basis)

    def measure_qubit(self, qubit: QubitState, measurement_basis: Basis) -> int:
        """Measure a qubit in the specified basis."""
        if qubit.basis == measurement_basis:
            return qubit.value

        return secrets.randbelow(2)

    def simulate_eavesdropping(
        self,
        qubits: list[QubitState],
    ) -> tuple[list[QubitState], list[Basis]]:
        """Simulate Eve's interception and measurement."""
        eve_bases = self.generate_random_bases(len(qubits))
        eve_measurements = []

        for qubit, eve_basis in zip(qubits, eve_bases):
            measured_value = self.measure_qubit(qubit, eve_basis)
            eve_measurements.append(QubitState(value=measured_value, basis=eve_basis))

        return eve_measurements, eve_bases

    def simulate_channel_loss(self, qubits: list[QubitState]) -> list[QubitState]:
        """Simulate photon loss in the quantum channel."""
        return [qubit for qubit in qubits if random.random() > self.channel_loss_rate]

    def run(self) -> QKDSimulationResult:
        """Run the BB84 simulation."""
        import time

        start_time = time.perf_counter()

        simulation_id = f"qkd_{uuid4().hex[:8]}"

        bits_to_send = self.key_length * 3

        alice_bits = self.generate_random_bits(bits_to_send)
        alice_bases = self.generate_random_bases(bits_to_send)

        alice_qubits = [self.encode_bit(bit, basis) for bit, basis in zip(alice_bits, alice_bases)]

        transmitted_qubits = self.simulate_channel_loss(alice_qubits)

        eve_intercepted = False
        if self.eavesdropper_rate > 0 and random.random() < self.eavesdropper_rate:
            transmitted_qubits, _ = self.simulate_eavesdropping(transmitted_qubits)
            eve_intercepted = True

        bob_bases = self.generate_random_bases(len(transmitted_qubits))
        bob_measurements = [
            self.measure_qubit(qubit, basis) for qubit, basis in zip(transmitted_qubits, bob_bases)
        ]

        alice_indices = []
        bob_indices = []
        for i, (alice_basis, bob_basis) in enumerate(zip(alice_bases, bob_bases)):
            if alice_basis == bob_basis:
                alice_indices.append(i)
                bob_indices.append(i)

        alice_sifted = [alice_bits[i] for i in alice_indices[: self.key_length]]
        bob_sifted = [bob_measurements[i] for i in bob_indices[: self.key_length]]

        error_count = sum(a != b for a, b in zip(alice_sifted, bob_sifted))
        error_rate = error_count / len(alice_sifted) if alice_sifted else 0

        eavesdropper_detected = error_rate > self.error_threshold

        test_bits = min(len(alice_sifted) // 3, 50)
        alice_test = alice_sifted[:test_bits]
        bob_test = bob_sifted[:test_bits]

        test_errors = sum(a != b for a, b in zip(alice_test, bob_test))
        test_error_rate = test_errors / len(alice_test) if alice_test else 0

        if test_error_rate > self.error_threshold:
            secure_key = []
            eavesdropper_detected = True
        else:
            secure_key = alice_sifted[test_bits:]

        alice_key_str = "".join(map(str, secure_key))
        bob_key_str = "".join(map(str, bob_sifted[test_bits:]))

        duration_ms = (time.perf_counter() - start_time) * 1000

        return QKDSimulationResult(
            simulation_id=simulation_id,
            protocol=QKDProtocol.BB84,
            alice_key=alice_key_str,
            bob_key=bob_key_str,
            sifted_key_length=len(alice_sifted),
            error_rate=error_rate,
            secure_key_length=len(secure_key),
            eavesdropper_detected=eavesdropper_detected,
            quantum_channel_losses=self.channel_loss_rate,
            classical_channel_uses=2,
            duration_ms=duration_ms,
        )


class E91Simulator:
    """Simulates the E91 (Ekert) QKD protocol using entangled pairs."""

    def __init__(
        self,
        key_length: int = 256,
        error_threshold: float = 0.15,
    ):
        self.key_length = key_length
        self.error_threshold = error_threshold

    def generate_entangled_pair(self) -> tuple[QubitState, QubitState]:
        """Generate an entangled Bell state |Φ+⟩ = (|00⟩ + |11⟩)/√2."""
        base_state = secrets.randbelow(2)
        return (
            QubitState(value=base_state, basis=Basis.RECTILINEAR),
            QubitState(value=base_state, basis=Basis.RECTILINEAR),
        )

    def measure_entangled(
        self,
        alice_qubit: QubitState,
        bob_qubit: QubitState,
        alice_basis: Basis,
        bob_basis: Basis,
    ) -> tuple[int, int]:
        """Measure entangled pair with correlation."""
        alice_result = self._measure_in_basis(alice_qubit, alice_basis)
        bob_result = self._measure_in_basis(bob_qubit, bob_basis)

        if alice_basis == bob_basis:
            bob_result = alice_result
        else:
            bob_result = secrets.randbelow(2)

        return alice_result, bob_result

    def _measure_in_basis(self, qubit: QubitState, basis: Basis) -> int:
        """Measure in specific basis."""
        if qubit.basis == basis:
            return qubit.value
        return secrets.randbelow(2)

    def run(self) -> QKDSimulationResult:
        """Run E91 simulation."""
        import time

        start_time = time.perf_counter()

        simulation_id = f"qkd_e91_{uuid4().hex[:8]}"

        alice_bases = [Basis.RECTILINEAR, Basis.DIAGONAL] * (self.key_length * 2)
        bob_bases = [Basis.DIAGONAL, Basis.RECTILINEAR] * (self.key_length * 2)

        alice_results = []
        bob_results = []

        for a_basis, b_basis in zip(alice_bases, bob_bases):
            alice_qubit, bob_qubit = self.generate_entangled_pair()
            a_result, b_result = self.measure_entangled(alice_qubit, bob_qubit, a_basis, b_basis)
            alice_results.append(a_result)
            bob_results.append(b_result)

        matching_indices = [i for i, (a, b) in enumerate(zip(alice_bases, bob_bases)) if a == b]

        alice_key_bits = [alice_results[i] for i in matching_indices[: self.key_length]]
        bob_key_bits = [bob_results[i] for i in matching_indices[: self.key_length]]

        error_count = sum(a != b for a, b in zip(alice_key_bits, bob_key_bits))
        error_rate = error_count / len(alice_key_bits) if alice_key_bits else 0

        bell_inequality_violation = 2.0 * (1 - 2 * error_rate)
        eavesdropper_detected = bell_inequality_violation < 2.0 * 0.707

        alice_key_str = "".join(map(str, alice_key_bits))
        bob_key_str = "".join(map(str, bob_key_bits))

        duration_ms = (time.perf_counter() - start_time) * 1000

        return QKDSimulationResult(
            simulation_id=simulation_id,
            protocol=QKDProtocol.E91,
            alice_key=alice_key_str,
            bob_key=bob_key_str,
            sifted_key_length=len(matching_indices),
            error_rate=error_rate,
            secure_key_length=len(alice_key_bits) if not eavesdropper_detected else 0,
            eavesdropper_detected=eavesdropper_detected,
            quantum_channel_losses=0.0,
            classical_channel_uses=3,
            duration_ms=duration_ms,
        )


class QKDSimulator:
    """Main QKD simulation interface."""

    def __init__(self):
        self._simulators = {
            QKDProtocol.BB84: BB84Simulator,
            QKDProtocol.E91: E91Simulator,
        }

    def simulate(
        self,
        protocol: QKDProtocol = QKDProtocol.BB84,
        key_length: int = 256,
        error_threshold: float = 0.11,
        channel_loss_rate: float = 0.05,
        eavesdropper_rate: float = 0.0,
        **kwargs,
    ) -> QKDSimulationResult:
        """Run a QKD simulation."""
        if protocol == QKDProtocol.BB84:
            simulator = BB84Simulator(
                key_length=key_length,
                error_threshold=error_threshold,
                channel_loss_rate=channel_loss_rate,
                eavesdropper_rate=eavesdropper_rate,
            )
        elif protocol == QKDProtocol.E91:
            simulator = E91Simulator(
                key_length=key_length,
                error_threshold=error_threshold,
            )
        else:
            raise ValueError(f"Unsupported protocol: {protocol}")

        return simulator.run()

    def compare_protocols(
        self,
        key_length: int = 256,
        iterations: int = 10,
    ) -> dict:
        """Compare different QKD protocols."""
        results = {}

        for protocol in [QKDProtocol.BB84, QKDProtocol.E91]:
            protocol_results = []
            for _ in range(iterations):
                result = self.simulate(protocol=protocol, key_length=key_length)
                protocol_results.append(result.to_dict())

            avg_error = sum(r["error_rate"] for r in protocol_results) / iterations
            avg_secure_len = sum(r["secure_key_length"] for r in protocol_results) / iterations

            results[protocol.value] = {
                "average_error_rate": avg_error,
                "average_secure_key_length": avg_secure_len,
                "iterations": iterations,
            }

        return results


qkd_simulator = QKDSimulator()
