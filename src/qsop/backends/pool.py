"""
Backend Pool for managing multiple quantum backends.
"""

from __future__ import annotations

import logging
from typing import Dict, List, Optional

from qsop.domain.ports.quantum_backend import QuantumBackend

logger = logging.getLogger(__name__)


class BackendPool:
    """
    Registry and manager for quantum backends.
    
    Allows registering, retrieving, and monitoring multiple backends
    from different providers.
    """
    
    def __init__(self, backends: Optional[List[QuantumBackend]] = None) -> None:
        self._backends: Dict[str, QuantumBackend] = {}
        if backends:
            for backend in backends:
                self.register(backend)
                
    def register(self, backend: QuantumBackend) -> None:
        """Register a new backend in the pool."""
        if backend.name in self._backends:
            logger.warning(f"Overwriting existing backend: {backend.name}")
        self._backends[backend.name] = backend
        logger.info(f"Registered backend: {backend.name}")
        
    def unregister(self, name: str) -> Optional[QuantumBackend]:
        """Remove a backend from the pool."""
        return self._backends.pop(name, None)
        
    def get_backend(self, name: str) -> Optional[QuantumBackend]:
        """Retrieve a backend by name."""
        return self._backends.get(name)
        
    def list_backends(self, only_online: bool = False) -> List[QuantumBackend]:
        """List all registered backends."""
        backends = list(self._backends.values())
        if only_online:
            return [b for b in backends if b.capabilities.online]
        return backends
        
    def __len__(self) -> int:
        return len(self._backends)

    def __contains__(self, name: str) -> bool:
        return name in self._backends
