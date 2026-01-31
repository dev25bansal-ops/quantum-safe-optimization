"""
Artifact domain models.

Defines structures for storing circuit artifacts, parameter snapshots,
and encrypted data blobs.
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any
from uuid import UUID, uuid4


class ArtifactType(Enum):
    """Types of artifacts that can be stored."""

    CIRCUIT = "circuit"
    PARAMETER_SNAPSHOT = "parameter_snapshot"
    RESULT = "result"
    LOG = "log"
    CUSTOM = "custom"


@dataclass(frozen=True)
class EncryptedBlob:
    """
    An encrypted data blob with associated metadata.

    Attributes:
        id: Unique identifier for the blob.
        ciphertext: The encrypted data.
        nonce: Nonce/IV used for encryption.
        tag: Authentication tag for AEAD ciphers.
        encapsulated_key: KEM-encapsulated symmetric key.
        kem_algorithm: Algorithm used for key encapsulation.
        symmetric_algorithm: Algorithm used for symmetric encryption.
        key_id: ID of the key used for encryption.
        created_at: When the blob was created.
        metadata: Additional unencrypted metadata.
    """

    id: UUID
    ciphertext: bytes
    nonce: bytes
    tag: bytes
    encapsulated_key: bytes
    kem_algorithm: str = "ML-KEM-768"
    symmetric_algorithm: str = "AES-256-GCM"
    key_id: str = ""
    created_at: datetime = field(default_factory=datetime.utcnow)
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def size_bytes(self) -> int:
        """Return the size of the ciphertext in bytes."""
        return len(self.ciphertext)


@dataclass(frozen=True)
class CircuitArtifact:
    """
    Artifact representing a quantum circuit.

    Attributes:
        id: Unique artifact identifier.
        job_id: ID of the job this circuit belongs to.
        name: Human-readable name for the circuit.
        circuit_type: Type of circuit (e.g., 'ansatz', 'measurement').
        num_qubits: Number of qubits in the circuit.
        depth: Circuit depth.
        gate_counts: Dictionary of gate types to counts.
        parameters: Named parameters in the circuit.
        encrypted_qasm: Encrypted OpenQASM representation.
        encrypted_data: Encrypted serialized circuit data.
        created_at: When the artifact was created.
        metadata: Additional circuit metadata.
    """

    id: UUID = field(default_factory=uuid4)
    job_id: UUID | None = None
    name: str = ""
    circuit_type: str = ""
    num_qubits: int = 0
    depth: int = 0
    gate_counts: dict[str, int] = field(default_factory=dict)
    parameters: tuple[str, ...] = ()
    encrypted_qasm: EncryptedBlob | None = None
    encrypted_data: EncryptedBlob | None = None
    created_at: datetime = field(default_factory=datetime.utcnow)
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def total_gates(self) -> int:
        """Return total number of gates in the circuit."""
        return sum(self.gate_counts.values())

    @property
    def is_parameterized(self) -> bool:
        """Check if the circuit has parameters."""
        return len(self.parameters) > 0

    @property
    def is_encrypted(self) -> bool:
        """Check if the circuit data is encrypted."""
        return self.encrypted_data is not None or self.encrypted_qasm is not None


@dataclass(frozen=True)
class ParameterSnapshot:
    """
    Snapshot of parameter values at a point in optimization.

    Attributes:
        id: Unique snapshot identifier.
        job_id: ID of the job this snapshot belongs to.
        iteration: Iteration number when snapshot was taken.
        parameters: Dictionary of parameter names to values.
        objective_value: Objective function value at these parameters.
        gradient: Gradient values (if available).
        constraint_values: Constraint function values.
        encrypted_data: Encrypted full parameter data.
        timestamp: When the snapshot was taken.
        metadata: Additional snapshot metadata.
    """

    id: UUID = field(default_factory=uuid4)
    job_id: UUID | None = None
    iteration: int = 0
    parameters: dict[str, float] = field(default_factory=dict)
    objective_value: float | None = None
    gradient: dict[str, float] | None = None
    constraint_values: dict[str, float] = field(default_factory=dict)
    encrypted_data: EncryptedBlob | None = None
    timestamp: datetime = field(default_factory=datetime.utcnow)
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def num_parameters(self) -> int:
        """Return the number of parameters in the snapshot."""
        return len(self.parameters)

    @property
    def is_encrypted(self) -> bool:
        """Check if the snapshot data is encrypted."""
        return self.encrypted_data is not None

    @property
    def has_gradient(self) -> bool:
        """Check if gradient information is available."""
        return self.gradient is not None and len(self.gradient) > 0
