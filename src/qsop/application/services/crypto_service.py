"""
Cryptographic service for the optimization platform.

Provides envelope encryption and signing for job artifacts.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from ...domain.ports.keystore import KeyStore, KeyType, KeyStatus
from ...crypto.envelopes.envelope import (
    EnvelopeEncryptor,
    EnvelopeDecryptor,
    EncryptedEnvelope,
    RecipientInfo,
)
from ...crypto.signing.signatures import Signer, Verifier, SignatureBundle, generate_keypair
from ...crypto.pqc import KEMAlgorithm, SignatureAlgorithm
from ...security.audit import AuditLogger
from ...security.compliance import ComplianceChecker, CompliancePolicy


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


class CryptoService:
    """
    Service for cryptographic operations on optimization artifacts.
    
    Provides envelope encryption using post-quantum KEMs and
    digital signatures using post-quantum signature schemes.
    """
    
    def __init__(
        self,
        keystore: KeyStore,
        policy: CryptoPolicy | None = None,
        audit_logger: AuditLogger | None = None,
        compliance_policy: CompliancePolicy | None = None,
    ):
        self.keystore = keystore
        self.policy = policy or CryptoPolicy()
        self.audit_logger = audit_logger
        self.compliance_policy = compliance_policy or CompliancePolicy.nist_l3()
        
        # Verify compliance of the current crypto policy
        self._verify_compliance()
    
    def _verify_compliance(self) -> None:
        """Verify that the current crypto policy meets compliance requirements."""
        checker = ComplianceChecker(self.compliance_policy)
        
        result = checker.check_operation(
            operation="initialize",
            kem_algorithm=self.policy.kem_algorithm,
            signature_algorithm=self.policy.signature_algorithm,
        )
        
        if not result.compliant:
            if self.audit_logger:
                self.audit_logger.log_compliance_violation(
                    violation_type="POLICY_INCOMPATIBLE",
                    description=f"Crypto policy does not meet compliance requirements: {'; '.join(result.issues)}",
                )
            result.raise_if_non_compliant()
    
    def generate_kem_keypair(self, key_id: str) -> KeyMaterial:
        """Generate a new KEM keypair for encryption."""
        from ...crypto.pqc import get_kem
        
        kem = get_kem(self.policy.kem_algorithm)
        public_key, private_key = kem.keygen()
        
        actual_key_id = self.keystore.store_key(
            key_type=KeyType.KEM,
            algorithm=self.policy.kem_algorithm.value,
            public_key=public_key,
            secret_key=private_key,
            key_id=key_id,
        )
        
        return KeyMaterial(
            key_id=actual_key_id,
            public_key=public_key,
            private_key=private_key,
            algorithm=self.policy.kem_algorithm.value,
        )
    
    def generate_signing_keypair(self, key_id: str) -> KeyMaterial:
        """Generate a new signing keypair."""
        public_key, private_key = generate_keypair(self.policy.signature_algorithm)
        
        actual_key_id = self.keystore.store_key(
            key_type=KeyType.SIGNATURE,
            algorithm=self.policy.signature_algorithm.value,
            public_key=public_key,
            secret_key=private_key,
            key_id=key_id,
        )
        
        return KeyMaterial(
            key_id=actual_key_id,
            public_key=public_key,
            private_key=private_key,
            algorithm=self.policy.signature_algorithm.value,
        )
    
    def encrypt_artifact(
        self,
        data: bytes,
        recipient_key_id: str,
        aad: bytes | None = None,
        actor_id: str = "system",
    ) -> EncryptedEnvelope:
        """
        Encrypt an artifact using envelope encryption.
        
        Args:
            data: The plaintext data to encrypt
            recipient_key_id: ID of the recipient's KEM public key
            aad: Additional authenticated data
            actor_id: ID of the actor performing the operation
            
        Returns:
            Encrypted envelope containing the ciphertext
        """
        try:
            public_key = self.keystore.get_public_key(recipient_key_id)
            
            encryptor = EnvelopeEncryptor(
                kem_algorithm=self.policy.kem_algorithm,
            )
            
            recipient = RecipientInfo(
                public_key=public_key,
                key_id=recipient_key_id,
            )
            
            envelope = encryptor.encrypt(data, recipients=[recipient])
            
            if self.audit_logger:
                self.audit_logger.log_crypto_operation(
                    operation="encapsulate",
                    actor_id=actor_id,
                    key_id=recipient_key_id,
                    success=True,
                    details={"algorithm": self.policy.kem_algorithm.value},
                )
            
            return envelope
        except Exception as e:
            if self.audit_logger:
                self.audit_logger.log_crypto_operation(
                    operation="encapsulate",
                    actor_id=actor_id,
                    key_id=recipient_key_id,
                    success=False,
                    details={"error": str(e)},
                )
            raise

    def decrypt_artifact(
        self,
        envelope: EncryptedEnvelope,
        key_id: str,
        actor_id: str = "system",
    ) -> bytes:
        """
        Decrypt an artifact.
        
        Args:
            envelope: The encrypted envelope
            key_id: ID of the decryption key
            actor_id: ID of the actor performing the operation
            
        Returns:
            Decrypted plaintext
        """
        try:
            private_key = self.keystore.get_secret_key(key_id)
            
            decryptor = EnvelopeDecryptor()
            
            plaintext = decryptor.decrypt(
                envelope,
                secret_key=private_key,
                key_id=key_id,
            )
            
            if self.audit_logger:
                self.audit_logger.log_crypto_operation(
                    operation="decapsulate",
                    actor_id=actor_id,
                    key_id=key_id,
                    success=True,
                )
            
            return plaintext
        except Exception as e:
            if self.audit_logger:
                self.audit_logger.log_crypto_operation(
                    operation="decapsulate",
                    actor_id=actor_id,
                    key_id=key_id,
                    success=False,
                    details={"error": str(e)},
                )
            raise

    def sign_artifact(
        self,
        data: Any,
        key_id: str,
        actor_id: str = "system",
    ) -> SignatureBundle:
        """
        Sign an artifact.
        
        Args:
            data: Data to sign (will be canonicalized)
            key_id: ID of the signing key
            actor_id: ID of the actor performing the operation
            
        Returns:
            Signature bundle
        """
        try:
            private_key = self.keystore.get_secret_key(key_id)
            
            signer = Signer(
                algorithm=self.policy.signature_algorithm,
                private_key=private_key,
                key_id=key_id,
            )
            
            bundle = signer.sign(data)
            
            if self.audit_logger:
                self.audit_logger.log_crypto_operation(
                    operation="sign",
                    actor_id=actor_id,
                    key_id=key_id,
                    success=True,
                    details={"algorithm": self.policy.signature_algorithm.value},
                )
            
            return bundle
        except Exception as e:
            if self.audit_logger:
                self.audit_logger.log_crypto_operation(
                    operation="sign",
                    actor_id=actor_id,
                    key_id=key_id,
                    success=False,
                    details={"error": str(e)},
                )
            raise

    def verify_signature(
        self,
        data: Any,
        bundle: SignatureBundle,
        actor_id: str = "system",
    ) -> bool:
        """
        Verify a signature.
        
        Args:
            data: The signed data
            bundle: The signature bundle
            actor_id: ID of the actor performing the operation
            
        Returns:
            True if signature is valid
        """
        try:
            public_key = self.keystore.get_public_key(bundle.key_id)
            
            verifier = Verifier(
                algorithm=bundle.algorithm,
                public_key=public_key,
            )
            
            is_valid = verifier.verify(data, bundle)
            
            if self.audit_logger:
                self.audit_logger.log_crypto_operation(
                    operation="verify",
                    actor_id=actor_id,
                    key_id=bundle.key_id,
                    success=is_valid,
                    details={"algorithm": bundle.algorithm},
                )
            
            return is_valid
        except Exception as e:
            if self.audit_logger:
                self.audit_logger.log_crypto_operation(
                    operation="verify",
                    actor_id=actor_id,
                    key_id=bundle.key_id,
                    success=False,
                    details={"error": str(e)},
                )
            return False
    
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
        ktype = KeyType.KEM if key_type == "kem" else KeyType.SIGNATURE
        
        self.keystore.store_key(
            key_type=ktype,
            algorithm=algorithm,
            public_key=public_key,
            secret_key=b"",  # No secret key for external public keys
            key_id=key_id,
        )


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
