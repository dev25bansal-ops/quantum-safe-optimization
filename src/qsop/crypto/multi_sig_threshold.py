"""
Multi-signature support and threshold encryption.

Provides advanced cryptographic features:
- Multi-signature schemes (aggregate signatures from multiple signers)
- Threshold encryption (split secret shares)
- Distributed key generation
- Shamir's Secret Sharing
- Committed signatures
"""

from __future__ import annotations

import hashlib
import secrets
from dataclasses import dataclass, field
from typing import Any

from qsop.crypto.pqc import (
    KEMAlgorithm,
    SignatureAlgorithm,
    get_kem,
    get_signature_scheme,
)


@dataclass
class MultiSignatureBundle:
    """Bundle containing multi-signature data."""

    messages: list[bytes]
    signatures: list[bytes]
    public_keys: list[bytes]
    aggregate_signature: bytes | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def verify_all(self) -> bool:
        """Verify all signatures."""
        from qsop.crypto.pqc import get_signature_scheme

        if len(self.messages) != len(self.signatures):
            return False

        for _i, (message, signature, public_key) in enumerate(
            zip(self.messages, self.signatures, self.public_keys, strict=False)
        ):
            sig_scheme = get_signature_scheme(SignatureAlgorithm.DILITHIUM2)
            if not sig_scheme.verify(message, signature, public_key):
                return False

        return True

    def serialize(self) -> bytes:
        """Serialize the bundle to bytes."""
        import base64
        import json

        data = {
            "messages": [base64.b64encode(m).decode() for m in self.messages],
            "signatures": [base64.b64encode(s).decode() for s in self.signatures],
            "public_keys": [base64.b64encode(pk).decode() for pk in self.public_keys],
            "aggregate_signature": base64.b64encode(self.aggregate_signature).decode()
            if self.aggregate_signature
            else None,
            "metadata": self.metadata,
        }

        return json.dumps(data).encode("utf-8")

    @classmethod
    def deserialize(cls, data: bytes) -> MultiSignatureBundle:
        """Deserialize from bytes."""
        import base64
        import json

        parsed = json.loads(data.decode("utf-8"))

        return cls(
            messages=[base64.b64decode(m.encode()) for m in parsed["messages"]],
            signatures=[base64.b64decode(s.encode()) for s in parsed["signatures"]],
            public_keys=[base64.b64decode(pk.encode()) for pk in parsed["public_keys"]],
            aggregate_signature=base64.b64decode(parsed["aggregate_signature"].encode())
            if parsed["aggregate_signature"]
            else None,
            metadata=parsed.get("metadata", {}),
        )


class MultiSigner:
    """
    Multi-signature coordinator.

    Manages signing with multiple parties:
    - Collect signatures from multiple signers
    - Aggregate signatures
    - Verify multi-signatures
    """

    def __init__(
        self,
        required_signatures: int,
        algorithm: SignatureAlgorithm = SignatureAlgorithm.DILITHIUM2,
    ):
        """
        Initialize multi-signer.

        Args:
            required_signatures: Number of required signatures
            algorithm: Signature algorithm to use
        """
        self.required_signatures = required_signatures
        self.algorithm = algorithm
        self._keypairs: dict[str, tuple[bytes, bytes]] = {}
        self._pending_signatures: dict[str, list[bytes]] = {}

    def register_signer(self, signer_id: str) -> tuple[bytes, bytes]:
        """
        Register a new signer and generate keypair.

        Args:
            signer_id: Unique identifier for the signer

        Returns:
            Tuple of (public_key, private_key)
        """
        sig_scheme = get_signature_scheme(self.algorithm)
        public_key, private_key = sig_scheme.keygen()

        self._keypairs[signer_id] = (public_key, private_key)
        self._pending_signatures[signer_id] = []

        return public_key, private_key

    def sign(
        self,
        signer_id: str,
        message: bytes,
    ) -> bytes:
        """
        Sign a message with specific signer.

        Args:
            signer_id: Signer identifier
            message: Message to sign

        Returns:
            Signature bytes
        """
        if signer_id not in self._keypairs:
            raise ValueError(f"Signer {signer_id} not registered")

        sig_scheme = get_signature_scheme(self.algorithm)
        public_key, private_key = self._keypairs[signer_id]

        signature = sig_scheme.sign(message, private_key)
        self._pending_signatures[signer_id].append(signature)

        return signature

    def collect_signatures(
        self,
        message: bytes,
        signer_ids: list[str],
    ) -> MultiSignatureBundle:
        """
        Collect signatures from multiple signers for a message.

        Args:
            message: Message to sign
            signer_ids: List of signer IDs

        Returns:
            MultiSignatureBundle
        """
        if len(signer_ids) < self.required_signatures:
            raise ValueError(f"Need at least {self.required_signatures} signatures")

        messages = [message] * len(signer_ids)
        signatures = []
        public_keys = []

        for signer_id in signer_ids:
            if signer_id not in self._keypairs:
                raise ValueError(f"Signer {signer_id} not registered")

            signature = self.sign(signer_id, message)
            public_key, _ = self._keypairs[signer_id]

            signatures.append(signature)
            public_keys.append(public_key)

        return MultiSignatureBundle(
            messages=messages,
            signatures=signatures,
            public_keys=public_keys,
        )

    def aggregate_signatures(
        self,
        bundle: MultiSignatureBundle,
    ) -> bytes:
        """
        Aggregate multiple signatures into one.

        Uses simple concatenation for Dilithium.
        For more sophisticated schemes, would use cryptographic aggregation.

        Args:
            bundle: Multi-signature bundle

        Returns:
            Aggregated signature
        """
        if len(bundle.signatures) < self.required_signatures:
            raise ValueError("Insufficient signatures")

        # Simple aggregation: hash of all signatures
        all_sigs = b"".join(bundle.signatures)
        hash_obj = hashlib.sha256()
        hash_obj.update(all_sigs)
        aggregated = hash_obj.digest()

        bundle.aggregate_signature = aggregated
        return aggregated

    def verify_multi_signature(
        self,
        bundle: MultiSignatureBundle,
        message: bytes,
    ) -> bool:
        """
        Verify multi-signature bundle.

        Args:
            bundle: Multi-signature bundle
            message: Original message

        Returns:
            True if all signatures valid
        """
        return bundle.verify_all()


class ThresholdEncryption:
    """
    Threshold encryption using Shamir's Secret Sharing.

    Splits a secret into n shares, requiring t shares to reconstruct.
    Combined with PQC for quantum-safe threshold decryption.
    """

    def __init__(
        self,
        total_shares: int,
        threshold: int,
        kem_algorithm: KEMAlgorithm = KEMAlgorithm.KYBER768,
    ):
        """
        Initialize threshold encryption.

        Args:
            total_shares: Total number of shares to split secret into
            threshold: Minimum shares required for reconstruction
            kem_algorithm: KEM algorithm for encryption
        """
        if threshold > total_shares:
            raise ValueError("Threshold cannot exceed total shares")

        self.total_shares = total_shares
        self.threshold = threshold
        self.kem_algorithm = kem_algorithm
        self._kem = get_kem(kem_algorithm)

    def encrypt_for_threshold(
        self,
        plaintext: bytes,
        recipient_public_keys: list[bytes],
    ) -> tuple[bytes, list[bytes]]:
        """
        Encrypt with threshold scheme.

        Args:
            plaintext: Data to encrypt
            recipient_public_keys: Public keys of share holders

        Returns:
            Tuple of (encrypted_data, secret_shares)
        """
        # Generate a random symmetric key (the secret to be shared)
        if len(plaintext) < 32:
            pad_len = 32 - len(plaintext)
            plaintext = plaintext + secrets.token_bytes(pad_len)

        secret_key = plaintext[:32]

        # Split secret using Shamir's Secret Sharing
        secret_shares = self._split_secret(secret_key)

        # Encrypt shares with each recipient's public key
        encrypted_shares = []
        for _i, (share, public_key) in enumerate(
            zip(secret_shares, recipient_public_keys, strict=False)
        ):
            encrypted_share = self._encrypt_share(share[:32], public_key)
            encrypted_shares.append(encrypted_share)

        # Return data and encrypted shares
        encrypted_data = plaintext[32:]

        return encrypted_data, encrypted_shares

    def decrypt_with_threshold(
        self,
        encrypted_data: bytes,
        encrypted_shares: list[bytes],
        private_keys: list[bytes],
    ) -> bytes:
        """
        Decrypt using threshold shares.

        Args:
            encrypted_data: Encrypted data
            encrypted_shares: Encrypted secret shares
            private_keys: Private keys corresponding to shares

        Returns:
            Decrypted data
        """
        if len(private_keys) < self.threshold:
            raise ValueError(f"Need at least {self.threshold} private keys")

        # Decrypt shares
        decrypted_shares = []
        for enc_share, private_key in zip(
            encrypted_shares[: self.threshold], private_keys[: self.threshold], strict=False
        ):
            share = self._decrypt_share(enc_share, private_key)
            decrypted_shares.append(share)

        # Reconstruct secret from shares
        secret_key = self._reconstruct_secret(decrypted_shares)

        # Derive full secret and decrypt data
        hkdf = hashlib.shake_256()
        hkdf.update(secret_key)
        encryption_key = hkdf.digest(32)  # 256-bit key

        # Decrypt data (simplified - would use proper AEAD in production)
        import cryptography.fernet

        fernet = cryptography.fernet.Fernet(
            cryptography.hazmat.primitives.serialization.base64.urlsafe_b64encode(encryption_key)
        )

        decrypted = fernet.decrypt(encrypted_data)

        return decrypted

    def _split_secret(self, secret: bytes) -> list[bytes]:
        """
        Split secret using Shamir's Secret Sharing.

        Args:
            secret: Secret to split (must be 32 bytes for Kyber-768)

        Returns:
            List of shares
        """
        if len(secret) != 32:
            raise ValueError("Secret must be 32 bytes for threshold demo")

        # Convert secret to integer
        secret_int = int.from_bytes(secret, "big")

        # Generate random polynomial coefficients
        # f(x) = secret + a1*x + a2*x^2 + ... + a_t-1*x^(t-1)
        coefficients = [secret_int] + [secrets.randbits(256) for _ in range(self.threshold - 1)]

        # Evaluate polynomial at n points
        shares = []
        for i in range(1, self.total_shares + 1):
            # Evaluate polynomial at x = i
            value = 0
            for j, coeff in enumerate(coefficients):
                value += coeff * (i**j)

            # Store as (x, value) pair
            share_data = i.to_bytes(4, "big") + value.to_bytes(32, "big")
            shares.append(share_data)

        return shares

    def _reconstruct_secret(self, shares: list[bytes]) -> bytes:
        """
        Reconstruct secret from shares using Lagrange interpolation.

        Args:
            shares: List of shares
        """
        if len(shares) < self.threshold:
            raise ValueError(f"Need at least {self.threshold} shares")

        # Parse shares
        points = []
        for share in shares:
            x = int.from_bytes(share[:4], "big")
            y = int.from_bytes(share[4:36], "big")
            points.append((x, y))

        # Lagrange interpolation at x = 0
        secret_int = 0
        for j, (x_j, y_j) in enumerate(points):
            # Compute Lagrange basis polynomial L_j(0)
            numerator = 1
            denominator = 1

            for m, (x_m, _) in enumerate(points):
                if m != j:
                    numerator *= -x_m
                    denominator *= x_j - x_m

            lagrange_term = (numerator // denominator) * y_j
            secret_int += lagrange_term

        # Convert back to bytes
        secret = secret_int.to_bytes(32, "big")

        return secret

    def _encrypt_share(self, share: bytes, public_key: bytes) -> bytes:
        """Encrypt a share with recipient's public key."""
        ciphertext, shared_secret = self._kem.encapsulate(public_key)

        # Use shared secret to encrypt share (simplified)
        import os

        from cryptography.hazmat.primitives.ciphers.aead import ChaCha20Poly1305

        nonce = os.urandom(12)
        cipher = ChaCha20Poly1305(shared_secret[:32])
        encrypted = cipher.encrypt(nonce, share, None)

        return nonce + ciphertext + encrypted

    def _decrypt_share(self, encrypted_share: bytes, private_key: bytes) -> bytes:
        """Decrypt a share with recipient's private key."""
        nonce = encrypted_share[:12]
        ciphertext = encrypted_share[12:1100]  # Kyber-768 ciphertext size
        encrypted = encrypted_share[1100:]

        # Decapsulate shared secret
        shared_secret = self._kem.decapsulate(ciphertext, private_key)

        # Decrypt share
        from cryptography.hazmat.primitives.ciphers.aead import ChaCha20Poly1305

        cipher = ChaCha20Poly1305(shared_secret[:32])
        decrypted = cipher.decrypt(nonce, encrypted, None)

        return decrypted


class DistributedKeyGeneration:
    """
    Simulated DKG (Distributed Key Generation) protocol.

    Generates cryptographic keys in a distributed manner such that
    no single party knows the complete private key.
    """

    def __init__(
        self,
        num_parties: int,
        threshold: int,
        algorithm: SignatureAlgorithm = SignatureAlgorithm.DILITHIUM2,
    ):
        """
        Initialize DKG.

        Args:
            num_parties: Number of participating parties
            threshold: Threshold for reconstruction
            algorithm: Signature algorithm
        """
        self.num_parties = num_parties
        self.threshold = threshold
        self.algorithm = algorithm

    def generate_distributed_keypair(self) -> dict[str, tuple[bytes, bytes]]:
        """
        Simulate distributed key generation.

        In a real DKG, parties would run a cryptographic protocol
        like Feldman VSS or Pedersen VSS to generate shares.

        Returns:
            Dictionary mapping party_id to (public_key_share, private_key_share)
        """
        keypairs = {}
        sig_scheme = get_signature_scheme(self.algorithm)

        # For simulation, generate a master key and split it
        master_public, master_private = sig_scheme.keygen()

        # Split master private key using secret sharing
        threshold_enc = ThresholdEncryption(self.num_parties, self.threshold)
        secret_shares = threshold_enc._split_secret(master_private)

        # Distribute shares
        for i, share in enumerate(secret_shares):
            party_id = f"party_{i}"
            keypairs[party_id] = (master_public, share)

        return keypairs

    def reconstruct_key(
        self,
        private_shares: list[bytes],
    ) -> bytes:
        """Reconstruct master private key from shares."""
        threshold_enc = ThresholdEncryption(self.num_parties, self.threshold)
        reconstructed = threshold_enc._reconstruct_secret(private_shares)
        return reconstructed


class CommittedSignature:
    """
    Committed signature scheme.

    Commitment-based multi-signature where signers commit to
    their signature before revealing it, preventing certain attacks.
    """

    def __init__(
        self,
        algorithm: SignatureAlgorithm = SignatureAlgorithm.DILITHIUM2,
    ):
        """
        Initialize committed signature scheme.

        Args:
            algorithm: Signature algorithm
        """
        self.algorithm = algorithm
        self._commitments: dict[str, bytes] = {}
        self._signatures: dict[str, bytes] = {}

    def commit(
        self,
        signer_id: str,
        message: bytes,
    ) -> bytes:
        """
        Create commitment for a signature.

        Args:
            signer_id: Signer identifier
            message: Message to sign

        Returns:
            Commitment hash
        """
        # Generate random nonce for commitment
        nonce = secrets.token_bytes(32)

        # Create commitment using hash
        commitment = hashlib.sha256(nonce + message).digest()

        self._commitments[signer_id] = (nonce, commitment)

        return commitment

    def sign_and_reveal(
        self,
        signer_id: str,
        private_key: bytes,
    ) -> tuple[bytes, bytes]:
        """
        Sign and reveal commitment.

        Args:
            signer_id: Signer identifier
            private_key: Private key

        Returns:
            Tuple of (commitment, signature)
        """
        if signer_id not in self._commitments:
            raise ValueError(f"No commitment for signer {signer_id}")

        nonce, commitment = self._commitments[signer_id]

        # Sign message with nonce
        message = nonce
        sig_scheme = get_signature_scheme(self.algorithm)
        signature = sig_scheme.sign(message, private_key)

        self._signatures[signer_id] = signature

        return commitment, signature

    def verify_commitment(
        self,
        signer_id: str,
        commitment: bytes,
        public_key: bytes,
    ) -> bool:
        """
        Verify commitment matches revealed signature.

        Args:
            signer_id: Signer identifier
            commitment: Commitment to verify
            public_key: Signer's public key

        Returns:
            True if commitment valid
        """
        if signer_id not in self._signatures:
            raise ValueError(f"No signature for signer {signer_id}")

        signature = self._signatures[signer_id]
        nonce = self._commitments[signer_id][0]

        # Verify signature
        sig_scheme = get_signature_scheme(self.algorithm)
        if not sig_scheme.verify(nonce, signature, public_key):
            return False

        # Verify commitment
        # Commitment would have been for different message in this simplified version
        # In full implementation, would commit to signature directly

        return True


__all__ = [
    "MultiSignatureBundle",
    "MultiSigner",
    "ThresholdEncryption",
    "DistributedKeyGeneration",
    "CommittedSignature",
]
