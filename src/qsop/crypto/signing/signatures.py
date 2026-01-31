"""
Post-quantum digital signature operations.

Provides signing and verification using Dilithium and SPHINCS+ algorithms.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from ..pqc import SignatureAlgorithm, get_signature_scheme


@dataclass(frozen=True)
class SignatureBundle:
    """Container for a signature with metadata."""
    
    signature: bytes
    algorithm: SignatureAlgorithm
    key_id: str
    timestamp: datetime
    canonical_hash: bytes
    
    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "signature": self.signature.hex(),
            "algorithm": self.algorithm.value,
            "key_id": self.key_id,
            "timestamp": self.timestamp.isoformat(),
            "canonical_hash": self.canonical_hash.hex(),
        }
    
    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> SignatureBundle:
        """Deserialize from dictionary."""
        return cls(
            signature=bytes.fromhex(data["signature"]),
            algorithm=SignatureAlgorithm(data["algorithm"]),
            key_id=data["key_id"],
            timestamp=datetime.fromisoformat(data["timestamp"]),
            canonical_hash=bytes.fromhex(data["canonical_hash"]),
        )


def canonicalize(data: Any) -> bytes:
    """
    Produce canonical byte representation for signing.
    
    Uses JSON canonical form (sorted keys, no whitespace) for dicts,
    UTF-8 encoding for strings, and identity for bytes.
    """
    if isinstance(data, bytes):
        return data
    if isinstance(data, str):
        return data.encode("utf-8")
    if isinstance(data, (dict, list)):
        # RFC 8785 JCS-style canonicalization
        return json.dumps(
            data,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        ).encode("utf-8")
    # For other types, convert to string first
    return str(data).encode("utf-8")


def compute_hash(data: bytes) -> bytes:
    """Compute SHA3-256 hash of data."""
    return hashlib.sha3_256(data).digest()


@dataclass
class Signer:
    """Signs data using post-quantum signature schemes."""
    
    algorithm: SignatureAlgorithm
    private_key: bytes
    key_id: str
    _scheme: Any = field(init=False, repr=False)
    
    def __post_init__(self) -> None:
        self._scheme = get_signature_scheme(self.algorithm)
    
    def sign(self, data: Any) -> SignatureBundle:
        """
        Sign arbitrary data.
        
        Data is canonicalized and hashed before signing.
        """
        canonical = canonicalize(data)
        data_hash = compute_hash(canonical)
        
        # Sign the hash
        signature = self._scheme.sign(data_hash, self.private_key)
        
        return SignatureBundle(
            signature=signature,
            algorithm=self.algorithm,
            key_id=self.key_id,
            timestamp=datetime.now(timezone.utc),
            canonical_hash=data_hash,
        )
    
    def sign_raw(self, message: bytes) -> bytes:
        """Sign raw bytes directly without canonicalization."""
        return self._scheme.sign(message, self.private_key)


@dataclass
class Verifier:
    """Verifies signatures using post-quantum signature schemes."""
    
    algorithm: SignatureAlgorithm
    public_key: bytes
    _scheme: Any = field(init=False, repr=False)
    
    def __post_init__(self) -> None:
        self._scheme = get_signature_scheme(self.algorithm)
    
    def verify(self, data: Any, bundle: SignatureBundle) -> bool:
        """
        Verify a signature bundle against data.
        
        Returns True if signature is valid, False otherwise.
        """
        if bundle.algorithm != self.algorithm:
            return False
        
        canonical = canonicalize(data)
        data_hash = compute_hash(canonical)
        
        # Verify hash matches
        if data_hash != bundle.canonical_hash:
            return False
        
        return self._scheme.verify(data_hash, bundle.signature, self.public_key)
    
    def verify_raw(self, message: bytes, signature: bytes) -> bool:
        """Verify raw signature without bundle."""
        return self._scheme.verify(message, signature, self.public_key)


def generate_keypair(
    algorithm: SignatureAlgorithm,
) -> tuple[bytes, bytes]:
    """
    Generate a new signing keypair.
    
    Returns:
        Tuple of (public_key, private_key)
    """
    scheme = get_signature_scheme(algorithm)
    return scheme.keygen()


class MultiSigner:
    """
    Aggregates multiple signatures for multi-party signing.
    """
    
    def __init__(self) -> None:
        self._signatures: list[SignatureBundle] = []
    
    def add_signature(self, bundle: SignatureBundle) -> None:
        """Add a signature to the collection."""
        self._signatures.append(bundle)
    
    def get_signatures(self) -> list[SignatureBundle]:
        """Get all collected signatures."""
        return list(self._signatures)
    
    def verify_all(
        self,
        data: Any,
        verifiers: dict[str, Verifier],
    ) -> dict[str, bool]:
        """
        Verify all signatures against data.
        
        Args:
            data: The data that was signed
            verifiers: Map of key_id -> Verifier
            
        Returns:
            Map of key_id -> verification result
        """
        results = {}
        for bundle in self._signatures:
            verifier = verifiers.get(bundle.key_id)
            if verifier is None:
                results[bundle.key_id] = False
            else:
                results[bundle.key_id] = verifier.verify(data, bundle)
        return results
    
    def to_dict(self) -> dict[str, Any]:
        """Serialize all signatures."""
        return {
            "signatures": [s.to_dict() for s in self._signatures],
        }
    
    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> MultiSigner:
        """Deserialize from dictionary."""
        ms = cls()
        for sig_data in data.get("signatures", []):
            ms.add_signature(SignatureBundle.from_dict(sig_data))
        return ms
