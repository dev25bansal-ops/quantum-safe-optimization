"""
Audit Log Integrity with ML-DSA Signing.

Provides cryptographic integrity for audit logs:
- Each log entry is signed with ML-DSA-65
- Tamper detection via signature verification
- Merkle tree for batch verification
- Chain linking for sequential integrity
"""

import base64
import hashlib
import json
import logging
import os
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

logger = logging.getLogger(__name__)


@dataclass
class SignedAuditEntry:
    """An audit log entry with ML-DSA signature."""

    event_id: str
    event_data: dict[str, Any]
    signature: str
    previous_hash: str
    current_hash: str
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    algorithm: str = "ML-DSA-65"

    def to_dict(self) -> dict[str, Any]:
        return {
            "event_id": self.event_id,
            "event_data": self.event_data,
            "signature": self.signature,
            "previous_hash": self.previous_hash,
            "current_hash": self.current_hash,
            "timestamp": self.timestamp.isoformat(),
            "algorithm": self.algorithm,
        }

    def verify(self, public_key: bytes) -> bool:
        """Verify the signature of this entry."""
        try:
            from quantum_safe_crypto import py_verify

            message = self._get_signing_message()
            return py_verify(public_key, message, self.signature, security_level=3)
        except ImportError:
            return self._verify_fallback(public_key)

    def _verify_fallback(self, public_key: bytes) -> bool:
        """Fallback verification using HMAC."""
        import hmac

        message = self._get_signing_message()
        expected_sig = hmac.new(public_key, message.encode(), hashlib.sha256).hexdigest()
        return hmac.compare_digest(self.signature[:64], expected_sig)

    def _get_signing_message(self) -> str:
        """Get the message to sign."""
        return json.dumps(
            {
                "event_id": self.event_id,
                "event_data": self.event_data,
                "previous_hash": self.previous_hash,
                "timestamp": self.timestamp.isoformat(),
            },
            sort_keys=True,
        )


class AuditIntegrityManager:
    """
    Manages audit log integrity with ML-DSA signatures.

    Features:
    - Sequential chain linking (each entry references previous)
    - ML-DSA-65 signatures for quantum-safe integrity
    - Merkle tree root for batch verification
    - Tamper detection
    """

    def __init__(self):
        self._signing_key: bytes | None = None
        self._public_key: bytes | None = None
        self._entries: list[SignedAuditEntry] = []
        self._last_hash: str = "0" * 64
        self._merkle_root: str | None = None

        self._initialize_keys()

    def _initialize_keys(self):
        """Initialize ML-DSA signing keys."""
        try:
            from quantum_safe_crypto import SigningKeyPair

            keypair = SigningKeyPair.generate(level=3)
            self._signing_key = keypair.secret_key
            self._public_key = keypair.public_key

            logger.info("Initialized ML-DSA-65 for audit log signing")

        except ImportError:
            self._signing_key = os.urandom(32)
            self._public_key = self._signing_key

            logger.warning("ML-DSA unavailable, using HMAC fallback for audit signing")

    def sign_event(self, event_data: dict[str, Any]) -> SignedAuditEntry:
        """Sign an audit event and add to chain."""
        event_id = f"audit_{uuid4().hex[:16]}"

        current_hash = self._compute_hash(event_id, event_data, self._last_hash)

        signature = self._sign_message(event_id, event_data, self._last_hash)

        entry = SignedAuditEntry(
            event_id=event_id,
            event_data=event_data,
            signature=signature,
            previous_hash=self._last_hash,
            current_hash=current_hash,
        )

        self._entries.append(entry)
        self._last_hash = current_hash

        self._update_merkle_root()

        return entry

    def _sign_message(self, event_id: str, event_data: dict, previous_hash: str) -> str:
        """Sign a message with ML-DSA."""
        message = json.dumps(
            {
                "event_id": event_id,
                "event_data": event_data,
                "previous_hash": previous_hash,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            },
            sort_keys=True,
        )

        try:
            from quantum_safe_crypto import py_sign

            signature = py_sign(self._signing_key, message, security_level=3)
            return signature

        except ImportError:
            import hmac

            sig = hmac.new(self._signing_key, message.encode(), hashlib.sha256).hexdigest()
            return sig

    def _compute_hash(self, event_id: str, event_data: dict, previous_hash: str) -> str:
        """Compute hash for chain linking."""
        data = json.dumps(
            {
                "event_id": event_id,
                "event_data": event_data,
                "previous_hash": previous_hash,
            },
            sort_keys=True,
        )

        return hashlib.sha256(data.encode()).hexdigest()

    def _update_merkle_root(self):
        """Update the Merkle tree root."""
        if not self._entries:
            self._merkle_root = None
            return

        hashes = [entry.current_hash for entry in self._entries[-1000:]]

        while len(hashes) > 1:
            new_hashes = []
            for i in range(0, len(hashes) - 1, 2):
                combined = hashes[i] + hashes[i + 1]
                new_hashes.append(hashlib.sha256(combined.encode()).hexdigest())
            if len(hashes) % 2 == 1:
                new_hashes.append(hashes[-1])
            hashes = new_hashes

        self._merkle_root = hashes[0] if hashes else None

    def verify_chain(self, start_index: int = 0) -> dict[str, Any]:
        """Verify the integrity of the audit chain."""
        errors = []
        verified_count = 0

        for i in range(start_index, len(self._entries)):
            entry = self._entries[i]

            if i > 0:
                expected_prev = self._entries[i - 1].current_hash
                if entry.previous_hash != expected_prev:
                    errors.append(
                        {
                            "index": i,
                            "event_id": entry.event_id,
                            "error": "Chain broken: previous_hash mismatch",
                        }
                    )

            computed_hash = self._compute_hash(
                entry.event_id, entry.event_data, entry.previous_hash
            )
            if computed_hash != entry.current_hash:
                errors.append(
                    {
                        "index": i,
                        "event_id": entry.event_id,
                        "error": "Hash mismatch: data may be tampered",
                    }
                )

            if not entry.verify(self._public_key):
                errors.append(
                    {
                        "index": i,
                        "event_id": entry.event_id,
                        "error": "Signature verification failed",
                    }
                )

            verified_count += 1

        return {
            "verified": len(errors) == 0,
            "verified_count": verified_count,
            "error_count": len(errors),
            "errors": errors[:10],
            "merkle_root": self._merkle_root,
        }

    def get_public_key(self) -> str:
        """Get the public key for verification."""
        return base64.b64encode(self._public_key).decode()

    def get_integrity_status(self) -> dict[str, Any]:
        """Get integrity status."""
        return {
            "entries_count": len(self._entries),
            "merkle_root": self._merkle_root,
            "last_hash": self._last_hash,
            "algorithm": "ML-DSA-65",
            "public_key": self.get_public_key(),
        }


_audit_integrity: AuditIntegrityManager | None = None


def get_audit_integrity() -> AuditIntegrityManager:
    """Get or create the audit integrity manager."""
    global _audit_integrity
    if _audit_integrity is None:
        _audit_integrity = AuditIntegrityManager()
    return _audit_integrity


def sign_audit_entry(event_data: dict[str, Any]) -> SignedAuditEntry:
    """Sign an audit event."""
    return get_audit_integrity().sign_event(event_data)


def verify_audit_chain() -> dict[str, Any]:
    """Verify audit chain integrity."""
    return get_audit_integrity().verify_chain()
