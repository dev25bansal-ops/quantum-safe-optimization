"""
Security module for the Quantum-Safe Optimization Platform.

Provides:
- Rate limiting to prevent brute-force attacks
- Token revocation for secure logout
- Request signature verification for encrypted payloads
"""

from .rate_limiter import limiter, RateLimits, create_rate_limit_decorator
from .token_revocation import (
    token_revocation_service,
    init_token_revocation,
    close_token_revocation,
)
from .signature_verification import (
    SignedPayload,
    SignatureVerificationResult,
    RequestSignatureVerifier,
    request_signature_verifier,
    verify_request_signature,
)

__all__ = [
    # Rate limiting
    "limiter",
    "RateLimits",
    "create_rate_limit_decorator",
    
    # Token revocation
    "token_revocation_service",
    "init_token_revocation",
    "close_token_revocation",
    
    # Signature verification
    "SignedPayload",
    "SignatureVerificationResult",
    "RequestSignatureVerifier",
    "request_signature_verifier",
    "verify_request_signature",
]
