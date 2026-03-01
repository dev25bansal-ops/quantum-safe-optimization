"""
Security module for the Quantum-Safe Optimization Platform.

Provides:
- Rate limiting to prevent brute-force attacks
- Token revocation for secure logout
- Request signature verification for encrypted payloads
"""

from .rate_limiter import RateLimits, create_rate_limit_decorator, limiter
from .signature_verification import (
    RequestSignatureVerifier,
    SignatureVerificationResult,
    SignedPayload,
    request_signature_verifier,
    verify_request_signature,
)
from .token_revocation import (
    close_token_revocation,
    init_token_revocation,
    token_revocation_service,
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
