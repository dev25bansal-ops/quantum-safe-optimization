"""Middleware for NIST security compliance validation."""

from __future__ import annotations

import json
import logging
from collections.abc import Callable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from qsop.crypto.pqc import KEMAlgorithm, SignatureAlgorithm
from qsop.security.compliance import ComplianceChecker, CompliancePolicy

logger = logging.getLogger(__name__)

# Mapping from common names/standard names to Enums
ALGO_MAP = {
    # KEMs
    "ML-KEM-512": KEMAlgorithm.KYBER512,
    "ML-KEM-768": KEMAlgorithm.KYBER768,
    "ML-KEM-1024": KEMAlgorithm.KYBER1024,
    "kyber512": KEMAlgorithm.KYBER512,
    "kyber768": KEMAlgorithm.KYBER768,
    "kyber1024": KEMAlgorithm.KYBER1024,
    "Kyber512": KEMAlgorithm.KYBER512,
    "Kyber768": KEMAlgorithm.KYBER768,
    "Kyber1024": KEMAlgorithm.KYBER1024,
    # Signatures
    "ML-DSA-44": SignatureAlgorithm.DILITHIUM2,
    "ML-DSA-65": SignatureAlgorithm.DILITHIUM3,
    "ML-DSA-87": SignatureAlgorithm.DILITHIUM5,
    "dilithium2": SignatureAlgorithm.DILITHIUM2,
    "dilithium3": SignatureAlgorithm.DILITHIUM3,
    "dilithium5": SignatureAlgorithm.DILITHIUM5,
    "Dilithium2": SignatureAlgorithm.DILITHIUM2,
    "Dilithium3": SignatureAlgorithm.DILITHIUM3,
    "Dilithium5": SignatureAlgorithm.DILITHIUM5,
    "sphincs-sha256-128f": SignatureAlgorithm.SPHINCS_SHA2_128s,
    "sphincs-sha256-128s": SignatureAlgorithm.SPHINCS_SHA2_128s,
    "sphincs-sha256-256f": SignatureAlgorithm.SPHINCS_SHA2_256f,
}


class ComplianceMiddleware(BaseHTTPMiddleware):
    """
    Middleware that validates job specifications against NIST Security Level 3.

    Specifically checks KEM and Signature algorithm choices in JobCreate requests.
    """

    def __init__(self, app, policy: CompliancePolicy | None = None) -> None:
        super().__init__(app)
        self.policy = policy or CompliancePolicy.nist_l3()
        self.checker = ComplianceChecker(self.policy)

    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Response]
    ) -> Response:
        # Only validate job creation and updates
        if request.method in ("POST", "PUT") and "/api/v1/jobs" in request.url.path:
            try:
                # We need to read the body without consuming it for the next handler
                body = await request.body()
                if not body:
                    return await call_next(request)

                data = json.loads(body)

                # Check for crypto settings
                crypto = data.get("crypto", {})
                kem_name = crypto.get("kem_algorithm")
                sig_name = crypto.get("signature_algorithm")

                # Also check in parameters as fallback/alternative
                params = data.get("parameters", {})
                if not kem_name:
                    kem_name = params.get("crypto", {}).get("kem_algorithm")
                if not sig_name:
                    sig_name = params.get("crypto", {}).get("signature_algorithm")

                # Map to Enums
                kem_algo = ALGO_MAP.get(kem_name) if kem_name else None
                sig_algo = ALGO_MAP.get(sig_name) if sig_name else None

                # If algorithms are specified, validate them
                if kem_algo or sig_algo:
                    result = self.checker.check_operation(
                        operation="submit_job", kem_algorithm=kem_algo, signature_algorithm=sig_algo
                    )

                    if not result.compliant:
                        logger.warning(
                            "compliance_violation",
                            path=request.url.path,
                            tenant_id=getattr(request.state, "tenant_id", "unknown"),
                            issues=result.issues,
                        )
                        return JSONResponse(
                            status_code=400,
                            content={
                                "error": "compliance_violation",
                                "message": f"Job specification does not meet {self.policy.name} requirements",
                                "details": result.issues,
                            },
                        )

                # Replace the request body with a new stream so the next handler can read it
                async def receive():
                    return {"type": "http.request", "body": body}

                # Create a new request with the buffered body
                new_request = Request(request.scope, receive=receive)
                return await call_next(new_request)

            except json.JSONDecodeError:
                # Let the normal validation handle bad JSON
                pass
            except Exception:
                logger.exception("Error in compliance middleware")
                # In case of error, we fail-safe by allowing the request but logging it
                # unless we want to be strictly secure and block.
                # Given the "Strengthen Security" request, blocking might be better.
                return JSONResponse(
                    status_code=500,
                    content={
                        "error": "security_check_error",
                        "message": "Failed to perform security compliance check",
                    },
                )

        return await call_next(request)
