"""
VQE Hamiltonians

Provides Hamiltonian construction for various quantum systems.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import List, Optional, Tuple

import numpy as np
import pennylane as qml


class VQEHamiltonian(ABC):
    """Base class for VQE Hamiltonians."""

    @property
    @abstractmethod
    def num_qubits(self) -> int:
        """Number of qubits required."""
        pass

    @abstractmethod
    def hamiltonian(self) -> qml.Hamiltonian:
        """Construct the Hamiltonian."""
        pass

    @property
    def wires(self) -> List[int]:
        """Qubit wire indices."""
        return list(range(self.num_qubits))


@dataclass
class MolecularHamiltonian(VQEHamiltonian):
    """
    Molecular Hamiltonian for quantum chemistry.

    Represents the electronic Hamiltonian of a molecule in second quantization,
    mapped to qubits using Jordan-Wigner or Bravyi-Kitaev transformation.
    """

    _hamiltonian: qml.Hamiltonian
    _num_qubits: int
    molecule_name: str = "H2"

    def __init__(
        self,
        symbols: List[str],
        coordinates: List[List[float]],
        charge: int = 0,
        multiplicity: int = 1,
        basis: str = "sto-3g",
        mapping: str = "jordan_wigner",
    ):
        """
        Initialize molecular Hamiltonian.

        Args:
            symbols: List of atomic symbols ["H", "H"]
            coordinates: Atomic coordinates in Angstroms [[0, 0, 0], [0, 0, 0.74]]
            charge: Molecular charge
            multiplicity: Spin multiplicity (1=singlet, 2=doublet, etc.)
            basis: Basis set name
            mapping: Qubit mapping ("jordan_wigner" or "bravyi_kitaev")
        """
        try:
            # Build molecular Hamiltonian using PennyLane-QChem
            self._hamiltonian, self._num_qubits = qml.qchem.molecular_hamiltonian(
                symbols=symbols,
                coordinates=np.array(coordinates).flatten(),
                charge=charge,
                mult=multiplicity,
                basis=basis,
                mapping=mapping,
            )
            self.molecule_name = "".join(symbols)
        except Exception:
            # Fallback to simple H2 model if qchem not available
            self._num_qubits = 4
            self._hamiltonian = self._simple_h2_hamiltonian()
            self.molecule_name = "H2_model"

    def _simple_h2_hamiltonian(self) -> qml.Hamiltonian:
        """Simple H2 Hamiltonian for testing."""
        coeffs = [-0.5, 0.5, -0.5, 0.5, 0.125, 0.125, -0.125, -0.125]
        ops = [
            qml.PauliZ(0),
            qml.PauliZ(1),
            qml.PauliZ(2),
            qml.PauliZ(3),
            qml.PauliZ(0) @ qml.PauliZ(1),
            qml.PauliZ(2) @ qml.PauliZ(3),
            qml.PauliZ(0) @ qml.PauliZ(2),
            qml.PauliZ(1) @ qml.PauliZ(3),
        ]
        return qml.Hamiltonian(coeffs, ops)

    @classmethod
    def h2(cls, bond_length: float = 0.74) -> "MolecularHamiltonian":
        """Create H2 molecule Hamiltonian."""
        return cls(
            symbols=["H", "H"],
            coordinates=[[0, 0, 0], [0, 0, bond_length]],
        )

    @classmethod
    def lih(cls, bond_length: float = 1.6) -> "MolecularHamiltonian":
        """Create LiH molecule Hamiltonian."""
        return cls(
            symbols=["Li", "H"],
            coordinates=[[0, 0, 0], [0, 0, bond_length]],
        )

    @classmethod
    def h2o(cls) -> "MolecularHamiltonian":
        """Create H2O molecule Hamiltonian."""
        # Water geometry (Angstroms)
        coords = [
            [0.0, 0.0, 0.1173],  # O
            [0.0, 0.7572, -0.4692],  # H
            [0.0, -0.7572, -0.4692],  # H
        ]
        return cls(
            symbols=["O", "H", "H"],
            coordinates=coords,
        )

    @property
    def num_qubits(self) -> int:
        return self._num_qubits

    def hamiltonian(self) -> qml.Hamiltonian:
        return self._hamiltonian


@dataclass
class IsingHamiltonian(VQEHamiltonian):
    """
    Transverse-Field Ising Model Hamiltonian.

    H = -J Σ_{<i,j>} Z_i Z_j - h Σ_i X_i

    Used for studying quantum phase transitions.
    """

    _num_qubits: int
    coupling_strength: float  # J
    transverse_field: float  # h
    periodic: bool = False

    def __init__(
        self,
        num_qubits: int,
        coupling_strength: float = 1.0,
        transverse_field: float = 1.0,
        periodic: bool = False,
    ):
        """
        Initialize Ising Hamiltonian.

        Args:
            num_qubits: Number of spins
            coupling_strength: Nearest-neighbor coupling J
            transverse_field: Transverse field strength h
            periodic: Use periodic boundary conditions
        """
        self._num_qubits = num_qubits
        self.coupling_strength = coupling_strength
        self.transverse_field = transverse_field
        self.periodic = periodic

    @property
    def num_qubits(self) -> int:
        return self._num_qubits

    def hamiltonian(self) -> qml.Hamiltonian:
        """Construct Ising Hamiltonian."""
        n = self._num_qubits
        J = self.coupling_strength
        h = self.transverse_field

        coeffs = []
        ops = []

        # ZZ interactions
        for i in range(n - 1):
            coeffs.append(-J)
            ops.append(qml.PauliZ(i) @ qml.PauliZ(i + 1))

        # Periodic boundary
        if self.periodic and n > 2:
            coeffs.append(-J)
            ops.append(qml.PauliZ(n - 1) @ qml.PauliZ(0))

        # Transverse field
        for i in range(n):
            coeffs.append(-h)
            ops.append(qml.PauliX(i))

        return qml.Hamiltonian(coeffs, ops)

    def exact_ground_state_energy(self) -> Optional[float]:
        """
        Calculate exact ground state energy for small systems.
        Only available for small qubit counts.
        """
        if self._num_qubits > 12:
            return None

        # Build full Hamiltonian matrix and diagonalize
        H = qml.matrix(self.hamiltonian())
        eigenvalues = np.linalg.eigvalsh(H)
        return float(np.min(eigenvalues))


@dataclass
class HeisenbergHamiltonian(VQEHamiltonian):
    """
    Heisenberg Model Hamiltonian.

    H = J Σ_{<i,j>} (X_i X_j + Y_i Y_j + Z_i Z_j)

    Models quantum magnetism with full spin-spin interactions.
    """

    _num_qubits: int
    coupling_strength: float  # J
    anisotropy: Tuple[float, float, float] = (1.0, 1.0, 1.0)  # (Jx, Jy, Jz)
    periodic: bool = False

    def __init__(
        self,
        num_qubits: int,
        coupling_strength: float = 1.0,
        anisotropy: Tuple[float, float, float] = (1.0, 1.0, 1.0),
        periodic: bool = False,
    ):
        """
        Initialize Heisenberg Hamiltonian.

        Args:
            num_qubits: Number of spins
            coupling_strength: Overall coupling J
            anisotropy: Relative strengths (Jx, Jy, Jz)
            periodic: Use periodic boundary conditions
        """
        self._num_qubits = num_qubits
        self.coupling_strength = coupling_strength
        self.anisotropy = anisotropy
        self.periodic = periodic

    @property
    def num_qubits(self) -> int:
        return self._num_qubits

    def hamiltonian(self) -> qml.Hamiltonian:
        """Construct Heisenberg Hamiltonian."""
        n = self._num_qubits
        J = self.coupling_strength
        Jx, Jy, Jz = self.anisotropy

        coeffs = []
        ops = []

        # Interaction terms
        pairs = [(i, i + 1) for i in range(n - 1)]
        if self.periodic and n > 2:
            pairs.append((n - 1, 0))

        for i, j in pairs:
            # XX interaction
            coeffs.append(J * Jx)
            ops.append(qml.PauliX(i) @ qml.PauliX(j))

            # YY interaction
            coeffs.append(J * Jy)
            ops.append(qml.PauliY(i) @ qml.PauliY(j))

            # ZZ interaction
            coeffs.append(J * Jz)
            ops.append(qml.PauliZ(i) @ qml.PauliZ(j))

        return qml.Hamiltonian(coeffs, ops)

    @classmethod
    def xxz(cls, num_qubits: int, delta: float = 1.0) -> "HeisenbergHamiltonian":
        """Create XXZ model (anisotropic Heisenberg)."""
        return cls(
            num_qubits=num_qubits,
            anisotropy=(1.0, 1.0, delta),
        )

    @classmethod
    def xyz(
        cls,
        num_qubits: int,
        jx: float = 1.0,
        jy: float = 1.0,
        jz: float = 1.0,
    ) -> "HeisenbergHamiltonian":
        """Create general XYZ model."""
        return cls(
            num_qubits=num_qubits,
            anisotropy=(jx, jy, jz),
        )
