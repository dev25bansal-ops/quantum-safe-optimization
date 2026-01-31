"""
Cryptographic service for the optimization platform.

Provides envelope encryption and signing for job artifacts.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from ...crypto.envelopes.envelope import (
    EnvelopeEncryptor,
    EnvelopeDecryptor,
    EncryptedEnvelope,
    RecipientInfo,
)
from ...crypto.signing.signatures import Signer, Verifier, SignatureBundle, generate_keypair
from ...crypto.pqc import KEMAlgorithm, SignatureAlgorithm


@dataclass
class CryptoPolicy:
    """Policy for cryptographic operations."""
    kem_algorithm: KEMAlgorithm = KEMAlgorithm.KYBER768
    signature_algorithm: SignatureAlgorithm = SignatureAlgorithm.DILITHIUM3
    require_signing: bool = True
    require_encryption: bool = True


@dataclass
class KeyMaterial:
    """Container for key material."""
    key_id: str
    public_key: bytes
    private_key: bytes | None = None
    algorithm: str = ""


@dataclass
class CryptoService:
    """
    Service for cryptographic operations on optimization artifacts.
    
    Provides envelope encryption using post-quantum KEMs and
    digital signatures using post-quantum signature schemes.
    """
    
    policy: CryptoPolicy = field(default_factory=CryptoPolicy)
    _kem_keys: dict[str, KeyMaterial] = field(default_factory=dict)
    _sig_keys: dict[str, KeyMaterial] = field(default_factory=dict)
    
    def generate_kem_keypair(self, key_id: str) -> KeyMaterial:
        """Generate a new KEM keypair for encryption."""
        from ...crypto.pqc import get_kem
        
        kem = get_kem(self.policy.kem_algorithm)
        public_key, private_key = kem.keygen()
        
        key_material = KeyMaterial(
            key_id=key_id,
            public_key=public_key,
            private_key=private_key,
            algorithm=self.policy.kem_algorithm.value,
        )
        
        self._kem_keys[key_id] = key_material
        return key_material
    
    def generate_signing_keypair(self, key_id: str) -> KeyMaterial:
        """Generate a new signing keypair."""
        public_key, private_key = generate_keypair(self.policy.signature_algorithm)
        
        key_material = KeyMaterial(
            key_id=key_id,
            public_key=public_key,
            private_key=private_key,
            algorithm=self.policy.signature_algorithm.value,
        )
        
        self._sig_keys[key_id] = key_material
        return key_material
    
    def encrypt_artifact(
        self,
        data: bytes,
        recipient_key_id: str,
        aad: bytes | None = None,
    ) -> EncryptedEnvelope:
        """
        Encrypt an artifact using envelope encryption.
        
        Args:
            data: The plaintext data to encrypt
            recipient_key_id: ID of the recipient's KEM public key
            aad: Additional authenticated data
            
        Returns:
            Encrypted envelope containing the ciphertext
        """
        key_material = self._kem_keys.get(recipient_key_id)
        if key_material is None:
            raise ValueError(f"Unknown key ID: {recipient_key_id}")
        
        encryptor = EnvelopeEncryptor(
            kem_algorithm=self.policy.kem_algorithm,
        )
        
        recipient = RecipientInfo(
            public_key=key_material.public_key,
            key_id=recipient_key_id,
        )
        
        return encryptor.encrypt(data, recipients=[recipient])
    
    def decrypt_artifact(
        self,
        envelope: EncryptedEnvelope,
        key_id: str,
    ) -> bytes:
        """
        Decrypt an artifact.
        
        Args:
            envelope: The encrypted envelope
            key_id: ID of the decryption key
            
        Returns:
            Decrypted plaintext
        """
        key_material = self._kem_keys.get(key_id)
        if key_material is None or key_material.private_key is None:
            raise ValueError(f"Private key not available for: {key_id}")
        
        decryptor = EnvelopeDecryptor()
        
        return decryptor.decrypt(
            envelope,
            secret_key=key_material.private_key,
            key_id=key_id,
        )
    
    def sign_artifact(
        self,
        data: Any,
        key_id: str,
    ) -> SignatureBundle:
        """
        Sign an artifact.
        
        Args:
            data: Data to sign (will be canonicalized)
            key_id: ID of the signing key
            
        Returns:
            Signature bundle
        """
        key_material = self._sig_keys.get(key_id)
        if key_material is None or key_material.private_key is None:
            raise ValueError(f"Signing key not available for: {key_id}")
        
        signer = Signer(
            algorithm=self.policy.signature_algorithm,
            private_key=key_material.private_key,
            key_id=key_id,
        )
        
        return signer.sign(data)
    
    def verify_signature(
        self,
        data: Any,
        bundle: SignatureBundle,
    ) -> bool:
        """
        Verify a signature.
        
        Args:
            data: The signed data
            bundle: The signature bundle
            
        Returns:
            True if signature is valid
        """
        key_material = self._sig_keys.get(bundle.key_id)
        if key_material is None:
            return False
        
        verifier = Verifier(
            algorithm=bundle.algorithm,
            public_key=key_material.public_key,
        )
        
        return verifier.verify(data, bundle)
    
    def encrypt_and_sign(
        self,
        data: bytes,
        encrypt_key_id: str,
        sign_key_id: str,
        aad: bytes | None = None,
    ) -> tuple[EncryptedEnvelope, SignatureBundle]:
        """
        Encrypt and sign an artifact (sign-then-encrypt).
        
        Args:
            data: Plaintext data
            encrypt_key_id: Recipient's encryption key ID
            sign_key_id: Sender's signing key ID
            aad: Additional authenticated data
            
        Returns:
            Tuple of (encrypted envelope, signature bundle)
        """
        # Sign first
        signature = self.sign_artifact(data, sign_key_id)
        
        # Then encrypt
        envelope = self.encrypt_artifact(data, encrypt_key_id, aad=aad)
        
        return envelope, signature
    
    def decrypt_and_verify(
        self,
        envelope: EncryptedEnvelope,
        signature: SignatureBundle,
        decrypt_key_id: str,
    ) -> tuple[bytes, bool]:
        """
        Decrypt and verify an artifact.
        
        Args:
            envelope: Encrypted envelope
            signature: Signature bundle
            decrypt_key_id: Decryption key ID
            
        Returns:
            Tuple of (plaintext, signature_valid)
        """
        # Decrypt first
        plaintext = self.decrypt_artifact(envelope, decrypt_key_id)
        
        # Then verify
        is_valid = self.verify_signature(plaintext, signature)
        
        return plaintext, is_valid
    
    def register_public_key(
        self,
        key_id: str,
        public_key: bytes,
        key_type: str,  # "kem" or "signature"
        algorithm: str,
    ) -> None:
        """Register an external public key."""
        key_material = KeyMaterial(
            key_id=key_id,
            public_key=public_key,
            algorithm=algorithm,
        )
        
        if key_type == "kem":
            self._kem_keys[key_id] = key_material
        elif key_type == "signature":
            self._sig_keys[key_id] = key_material
        else:
            raise ValueError(f"Unknown key type: {key_type}")


class SecureJobHandler:
    """
    Handler for secure job submission and retrieval.
    
    Wraps job artifacts with encryption and signatures.
    """
    
    def __init__(self, crypto_service: CryptoService):
        self.crypto = crypto_service
    
    def secure_job_spec(
        self,
        job_spec: dict,
        tenant_key_id: str,
        platform_sign_key_id: str,
    ) -> dict:
        """
        Secure a job specification before storage.
        
        Returns a secured bundle with encrypted sensitive data
        and a signature for integrity.
        """
        import json
        
        # Serialize job spec
        spec_bytes = json.dumps(job_spec, sort_keys=True).encode("utf-8")
        
        # Encrypt and sign
        envelope, signature = self.crypto.encrypt_and_sign(
            spec_bytes,
            encrypt_key_id=tenant_key_id,
            sign_key_id=platform_sign_key_id,
        )
        
        return {
            "envelope": envelope.to_dict(),
            "signature": signature.to_dict(),
        }
    
    def unsecure_job_spec(
        self,
        secured_bundle: dict,
        tenant_key_id: str,
    ) -> tuple[dict, bool]:
        """
        Decrypt and verify a secured job specification.
        
        Returns the job spec and verification status.
        """
        import json
        
        envelope = EncryptedEnvelope.from_dict(secured_bundle["envelope"])
        signature = SignatureBundle.from_dict(secured_bundle["signature"])
        
        plaintext, is_valid = self.crypto.decrypt_and_verify(
            envelope,
            signature,
            decrypt_key_id=tenant_key_id,
        )
        
        job_spec = json.loads(plaintext.decode("utf-8"))
        
        return job_spec, is_valid
