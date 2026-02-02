"""
Request signature verification for encrypted payloads.

Verifies ML-DSA signatures on encrypted payloads to ensure authenticity
and integrity before decryption.
"""

from typing import Optional, Tuple
from dataclasses import dataclass
from pydantic import BaseModel, Field
import base64
import json

from quantum_safe_crypto import SigningKeyPair, py_verify


class SignedPayload(BaseModel):
    """
    A signed encrypted payload with ML-DSA signature.
    
    Structure:
    - payload: The encrypted data (EncryptedEnvelope as base64 JSON)
    - signature: ML-DSA-65 signature over the payload
    - signer_public_key: Public key of the signer (for verification)
    """
    payload: str = Field(..., description="Encrypted payload as base64 JSON")
    signature: str = Field(..., description="ML-DSA-65 signature (base64)")
    signer_public_key: str = Field(..., description="Signer's public key (base64)")
    timestamp: Optional[float] = Field(None, description="Unix timestamp of signing")
    nonce: Optional[str] = Field(None, description="Anti-replay nonce")


@dataclass
class SignatureVerificationResult:
    """Result of signature verification."""
    valid: bool
    error: Optional[str] = None
    payload_data: Optional[bytes] = None
    signer_key: Optional[str] = None


class RequestSignatureVerifier:
    """
    Verifies ML-DSA signatures on encrypted API payloads.
    
    Features:
    - Verifies signature authenticity
    - Checks timestamp freshness (optional)
    - Anti-replay protection via nonce tracking
    """
    
    def __init__(
        self,
        max_age_seconds: int = 300,  # 5 minutes
        require_timestamp: bool = True,
        require_nonce: bool = False,
    ):
        self.max_age_seconds = max_age_seconds
        self.require_timestamp = require_timestamp
        self.require_nonce = require_nonce
        self._seen_nonces: set = set()  # In production, use Redis
    
    def verify_signature(
        self,
        signed_payload: SignedPayload,
        expected_signer_key: Optional[str] = None,
    ) -> SignatureVerificationResult:
        """
        Verify the signature on a signed payload.
        
        Args:
            signed_payload: The signed payload to verify
            expected_signer_key: If provided, verify signer matches
            
        Returns:
            SignatureVerificationResult with verification status
        """
        import time
        
        # Check timestamp if required
        if self.require_timestamp:
            if signed_payload.timestamp is None:
                return SignatureVerificationResult(
                    valid=False,
                    error="Timestamp required but not provided"
                )
            
            current_time = time.time()
            age = abs(current_time - signed_payload.timestamp)
            if age > self.max_age_seconds:
                return SignatureVerificationResult(
                    valid=False,
                    error=f"Request timestamp too old ({age:.1f}s > {self.max_age_seconds}s)"
                )
        
        # Check nonce for replay protection
        if self.require_nonce:
            if signed_payload.nonce is None:
                return SignatureVerificationResult(
                    valid=False,
                    error="Nonce required but not provided"
                )
            if signed_payload.nonce in self._seen_nonces:
                return SignatureVerificationResult(
                    valid=False,
                    error="Replay detected: nonce already used"
                )
            self._seen_nonces.add(signed_payload.nonce)
        
        # Check signer key matches expected
        if expected_signer_key and signed_payload.signer_public_key != expected_signer_key:
            return SignatureVerificationResult(
                valid=False,
                error="Signer public key does not match expected key"
            )
        
        try:
            # Decode signature
            signature_bytes = base64.b64decode(signed_payload.signature)
            
            # Construct the signed data (payload + optional metadata)
            signed_data = signed_payload.payload
            if signed_payload.timestamp is not None:
                signed_data += f":{signed_payload.timestamp}"
            if signed_payload.nonce is not None:
                signed_data += f":{signed_payload.nonce}"
            
            # Verify with ML-DSA-65
            is_valid = py_verify(
                signed_data.encode('utf-8'),
                signed_payload.signature,
                signed_payload.signer_public_key,
            )
            
            if not is_valid:
                return SignatureVerificationResult(
                    valid=False,
                    error="Signature verification failed"
                )
            
            # Decode the payload
            payload_data = base64.b64decode(signed_payload.payload)
            
            return SignatureVerificationResult(
                valid=True,
                payload_data=payload_data,
                signer_key=signed_payload.signer_public_key,
            )
            
        except Exception as e:
            return SignatureVerificationResult(
                valid=False,
                error=f"Verification error: {str(e)}"
            )
    
    def create_signed_payload(
        self,
        data: bytes,
        signing_keypair: SigningKeyPair,
        include_timestamp: bool = True,
        include_nonce: bool = False,
    ) -> SignedPayload:
        """
        Create a signed payload for sending to the API.
        
        Args:
            data: The data to sign (usually encrypted envelope)
            signing_keypair: The signing key pair to use
            include_timestamp: Whether to include timestamp
            include_nonce: Whether to include anti-replay nonce
            
        Returns:
            SignedPayload ready for transmission
        """
        import time
        import secrets
        
        # Encode payload
        payload_b64 = base64.b64encode(data).decode('utf-8')
        
        # Build signed data
        timestamp = time.time() if include_timestamp else None
        nonce = secrets.token_hex(16) if include_nonce else None
        
        signed_data = payload_b64
        if timestamp is not None:
            signed_data += f":{timestamp}"
        if nonce is not None:
            signed_data += f":{nonce}"
        
        # Sign with ML-DSA-65
        signature = signing_keypair.sign(signed_data.encode('utf-8'))
        
        return SignedPayload(
            payload=payload_b64,
            signature=signature,
            signer_public_key=signing_keypair.public_key,
            timestamp=timestamp,
            nonce=nonce,
        )


# Global verifier instance with default settings
request_signature_verifier = RequestSignatureVerifier(
    max_age_seconds=300,  # 5 minutes
    require_timestamp=True,
    require_nonce=False,
)


def verify_request_signature(signed_payload: SignedPayload) -> SignatureVerificationResult:
    """Convenience function for verifying request signatures."""
    return request_signature_verifier.verify_signature(signed_payload)
