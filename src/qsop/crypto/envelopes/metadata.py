"""
Envelope metadata and AAD (Additional Authenticated Data) conventions.
"""

import json
import hashlib
from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import Optional, Dict, Any, List
from datetime import datetime, timezone


class EnvelopeVersion(Enum):
    """Envelope format version."""
    
    V1 = "1.0"


@dataclass
class EnvelopeMetadata:
    """
    Metadata for encrypted envelopes.
    
    This metadata is included in the AAD and authenticated but not encrypted.
    """
    
    version: str = EnvelopeVersion.V1.value
    kem_algorithm: Optional[str] = None
    aead_algorithm: Optional[str] = None
    created_at: Optional[str] = None
    key_id: Optional[str] = None
    content_type: Optional[str] = None
    recipient_count: int = 1
    custom: Dict[str, Any] = field(default_factory=dict)
    
    def __post_init__(self):
        if self.created_at is None:
            self.created_at = datetime.now(timezone.utc).isoformat()
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary, excluding None values."""
        result = {}
        for key, value in asdict(self).items():
            if value is not None and value != {}:
                result[key] = value
        return result
    
    def to_json(self) -> str:
        """Convert to canonical JSON string."""
        return json.dumps(
            self.to_dict(),
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
        )
    
    def to_bytes(self) -> bytes:
        """Convert to canonical bytes for AAD."""
        return self.to_json().encode("utf-8")
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "EnvelopeMetadata":
        """Create from dictionary."""
        return cls(
            version=data.get("version", EnvelopeVersion.V1.value),
            kem_algorithm=data.get("kem_algorithm"),
            aead_algorithm=data.get("aead_algorithm"),
            created_at=data.get("created_at"),
            key_id=data.get("key_id"),
            content_type=data.get("content_type"),
            recipient_count=data.get("recipient_count", 1),
            custom=data.get("custom", {}),
        )
    
    @classmethod
    def from_json(cls, json_str: str) -> "EnvelopeMetadata":
        """Create from JSON string."""
        return cls.from_dict(json.loads(json_str))
    
    @classmethod
    def from_bytes(cls, data: bytes) -> "EnvelopeMetadata":
        """Create from bytes."""
        return cls.from_json(data.decode("utf-8"))


@dataclass
class EnvelopeHeader:
    """
    Complete envelope header structure.
    
    Contains all information needed to identify and process an envelope.
    """
    
    metadata: EnvelopeMetadata
    recipient_key_ids: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "metadata": self.metadata.to_dict(),
            "recipient_key_ids": self.recipient_key_ids,
        }
    
    def to_json(self) -> str:
        """Convert to canonical JSON string."""
        return json.dumps(
            self.to_dict(),
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
        )
    
    def to_bytes(self) -> bytes:
        """Convert to bytes."""
        return self.to_json().encode("utf-8")
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "EnvelopeHeader":
        """Create from dictionary."""
        return cls(
            metadata=EnvelopeMetadata.from_dict(data.get("metadata", {})),
            recipient_key_ids=data.get("recipient_key_ids", []),
        )
    
    @classmethod
    def from_bytes(cls, data: bytes) -> "EnvelopeHeader":
        """Create from bytes."""
        return cls.from_dict(json.loads(data.decode("utf-8")))


def build_aad(
    metadata: EnvelopeMetadata,
    recipient_public_keys: Optional[List[bytes]] = None,
    additional_context: Optional[bytes] = None,
) -> bytes:
    """
    Build AAD (Additional Authenticated Data) for envelope encryption.
    
    The AAD binds the ciphertext to its context, preventing misuse attacks.
    
    AAD structure:
        - Canonical JSON of metadata
        - Hash of recipient public keys (if provided)
        - Additional context (if provided)
    
    Args:
        metadata: Envelope metadata.
        recipient_public_keys: List of recipient public keys to bind.
        additional_context: Additional application-specific context.
    
    Returns:
        AAD bytes.
    """
    parts = [metadata.to_bytes()]
    
    if recipient_public_keys:
        # Hash concatenated public keys to bind ciphertext to recipients
        key_data = b"".join(sorted(recipient_public_keys))
        key_hash = hashlib.sha256(key_data).digest()
        parts.append(key_hash)
    
    if additional_context:
        if not isinstance(additional_context, bytes):
            raise TypeError("additional_context must be bytes")
        parts.append(additional_context)
    
    # Combine with length prefixes for unambiguous parsing
    aad = b""
    for part in parts:
        length_prefix = len(part).to_bytes(4, "big")
        aad += length_prefix + part
    
    return aad


def parse_aad(aad: bytes) -> List[bytes]:
    """
    Parse AAD into its component parts.
    
    Args:
        aad: AAD bytes created by build_aad.
    
    Returns:
        List of component parts.
    """
    parts = []
    offset = 0
    
    while offset < len(aad):
        if offset + 4 > len(aad):
            raise ValueError("Invalid AAD: truncated length prefix")
        
        length = int.from_bytes(aad[offset:offset + 4], "big")
        offset += 4
        
        if offset + length > len(aad):
            raise ValueError("Invalid AAD: truncated part")
        
        parts.append(aad[offset:offset + length])
        offset += length
    
    return parts


__all__ = [
    "EnvelopeVersion",
    "EnvelopeMetadata",
    "EnvelopeHeader",
    "build_aad",
    "parse_aad",
]
