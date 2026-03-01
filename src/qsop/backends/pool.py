"""
Backend Pool for managing multiple quantum backends.
"""

from __future__ import annotations

import logging

from qsop.domain.ports.quantum_backend import QuantumBackend

logger = logging.getLogger(__name__)


class BackendPool:
    """
    Registry and manager for quantum backends.

    Allows registering, retrieving, and monitoring multiple backends
    from different providers.
    """

    def __init__(self, backends: list[QuantumBackend] | None = None) -> None:
        self._backends: dict[str, QuantumBackend] = {}
        if backends:
            for backend in backends:
                self.register(backend)

    def register(self, backend: QuantumBackend) -> None:
        """Register a new backend in the pool."""
        if backend.name in self._backends:
            logger.warning(f"Overwriting existing backend: {backend.name}")
        self._backends[backend.name] = backend
        logger.info(f"Registered backend: {backend.name}")

    def unregister(self, name: str) -> QuantumBackend | None:
        """Remove a backend from the pool."""
        return self._backends.pop(name, None)

    def get_backend(self, name: str) -> QuantumBackend | None:
        """Retrieve a backend by name."""
        return self._backends.get(name)

    def list_backends(
        self,
        only_online: bool = False,
        simulator: bool | None = None,
        local: bool | None = None,
        min_qubits: int | None = None,
    ) -> list[QuantumBackend]:
        """
        List registered backends with optional filtering.
        """
        backends = list(self._backends.values())

        if only_online:
            backends = [b for b in backends if b.capabilities.online]
        if simulator is not None:
            backends = [b for b in backends if b.capabilities.simulator == simulator]
        if local is not None:
            backends = [b for b in backends if b.capabilities.local == local]
        if min_qubits is not None:
            backends = [b for b in backends if b.capabilities.num_qubits >= min_qubits]

        return backends

    def get_backends_by_capability(self, **criteria: Any) -> list[QuantumBackend]:
        """
        Find backends matching specific capability criteria.

        Example:
            pool.get_backends_by_capability(num_qubits=5, simulator=False)
        """
        matches = []
        for backend in self._backends.values():
            caps = backend.capabilities
            is_match = True
            for key, value in criteria.items():
                if not hasattr(caps, key) or getattr(caps, key) != value:
                    is_match = False
                    break
            if is_match:
                matches.append(backend)
        return matches

    def __len__(self) -> int:
        return len(self._backends)

    def __contains__(self, name: str) -> bool:
        return name in self._backends
