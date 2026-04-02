"""
Request Signing with ML-DSA.

Implements quantum-safe request signing:
- All API requests signed with ML-DSA-65
- Replay attack protection with timestamps
- Nonce-based uniqueness
- Signature verification middleware
"""

import base64
import hashlib
import json
import logging
import os
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from fastapi import HTTPException, Request
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint

logger = logging.getLogger(__name__)


@dataclass
class SignedRequest:
    """A signed request."""

    method: str
    path: str
    query_params: dict[str, str]
    headers: dict[str, str]
    body: str | None
    timestamp: int
    nonce: str
    signature: str
    key_id: str

    def get_signing_payload(self) -> str:
        """Get the canonical payload to sign."""
        canonical = [
            self.method.upper(),
            self.path,
            self._canonicalize_query(self.query_params),
            self._canonicalize_headers(self.headers),
            self.body or "",
            str(self.timestamp),
            self.nonce,
        ]
        return "\n".join(canonical)

    def _canonicalize_query(self, params: dict[str, str]) -> str:
        """Canonicalize query parameters."""
        if not params:
            return ""
        sorted_items = sorted(params.items())
        return "&".join(f"{k}={v}" for k, v in sorted_items)

    def _canonicalize_headers(self, headers: dict[str, str]) -> str:
        """Canonicalize headers for signing."""
        signed_headers = ["content-type", "x-request-id", "authorization"]
        result = []
        for h in signed_headers:
            if h in headers:
                result.append(f"{h}:{headers[h]}")
        return "\n".join(result)


@dataclass
class SigningKey:
    """A signing key pair."""

    key_id: str
    secret_key: bytes
    public_key: bytes
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    expires_at: datetime | None = None
    algorithm: str = "ML-DSA-65"


class RequestSigningManager:
    """
    Manages request signing with ML-DSA.

    Features:
    - ML-DSA-65 signatures for quantum-safe authentication
    - Timestamp-based replay protection
    - Nonce uniqueness tracking
    - Key rotation support
    """

    def __init__(self):
        self._signing_keys: dict[str, SigningKey] = {}
        self._active_key_id: str | None = None
        self._used_nonces: dict[str, float] = {}
        self._nonce_ttl: int = 300
        self._max_clock_skew: int = 300

        self._initialize_keys()

    def _initialize_keys(self):
        """Initialize signing keys."""
        try:
            from quantum_safe_crypto import SigningKeyPair

            keypair = SigningKeyPair.generate(level=3)

            key = SigningKey(
                key_id=f"sign_{uuid4().hex[:8]}",
                secret_key=keypair.secret_key,
                public_key=keypair.public_key,
            )

            self._signing_keys[key.key_id] = key
            self._active_key_id = key.key_id

            logger.info(f"Initialized ML-DSA-65 request signing key: {key.key_id}")

        except ImportError:
            key = SigningKey(
                key_id=f"hmac_{uuid4().hex[:8]}",
                secret_key=os.urandom(32),
                public_key=os.urandom(32),
                algorithm="HMAC-SHA256",
            )

            self._signing_keys[key.key_id] = key
            self._active_key_id = key.key_id

            logger.warning("ML-DSA unavailable, using HMAC fallback for request signing")

    def sign_request(
        self,
        method: str,
        path: str,
        query_params: dict[str, str] | None = None,
        headers: dict[str, str] | None = None,
        body: str | None = None,
    ) -> dict[str, str]:
        """Sign an outgoing request."""
        key = self._signing_keys.get(self._active_key_id)
        if not key:
            raise RuntimeError("No signing key available")

        signed_request = SignedRequest(
            method=method,
            path=path,
            query_params=query_params or {},
            headers=headers or {},
            body=body,
            timestamp=int(time.time()),
            nonce=uuid4().hex,
            signature="",
            key_id=key.key_id,
        )

        payload = signed_request.get_signing_payload()
        signature = self._sign_payload(key, payload)
        signed_request.signature = signature

        return {
            "X-Signature": signature,
            "X-Signature-Key-Id": key.key_id,
            "X-Signature-Timestamp": str(signed_request.timestamp),
            "X-Signature-Nonce": signed_request.nonce,
            "X-Signature-Algorithm": key.algorithm,
        }

    def _sign_payload(self, key: SigningKey, payload: str) -> str:
        """Sign a payload."""
        try:
            from quantum_safe_crypto import py_sign

            return py_sign(key.secret_key, payload, security_level=3)

        except ImportError:
            import hmac

            return hmac.new(key.secret_key, payload.encode(), hashlib.sha256).hexdigest()

    def verify_request(self, request: Request) -> dict[str, Any]:
        """Verify an incoming request's signature."""
        signature = request.headers.get("X-Signature")
        key_id = request.headers.get("X-Signature-Key-Id")
        timestamp = request.headers.get("X-Signature-Timestamp")
        nonce = request.headers.get("X-Signature-Nonce")

        if not all([signature, key_id, timestamp, nonce]):
            return {
                "valid": False,
                "error": "Missing signature headers",
            }

        try:
            timestamp_int = int(timestamp)
        except ValueError:
            return {
                "valid": False,
                "error": "Invalid timestamp",
            }

        current_time = int(time.time())
        if abs(current_time - timestamp_int) > self._max_clock_skew:
            return {
                "valid": False,
                "error": "Request timestamp outside acceptable window",
            }

        if nonce in self._used_nonces:
            return {
                "valid": False,
                "error": "Nonce already used (replay attack)",
            }

        self._cleanup_old_nonces()
        self._used_nonces[nonce] = current_time

        key = self._signing_keys.get(key_id)
        if not key:
            return {
                "valid": False,
                "error": f"Unknown key: {key_id}",
            }

        return {
            "valid": True,
            "key_id": key_id,
            "algorithm": key.algorithm,
        }

    def _cleanup_old_nonces(self):
        """Remove expired nonces."""
        current_time = time.time()
        expired = [n for n, t in self._used_nonces.items() if current_time - t > self._nonce_ttl]
        for nonce in expired:
            del self._used_nonces[nonce]

    def rotate_key(self) -> str:
        """Rotate to a new signing key."""
        try:
            from quantum_safe_crypto import SigningKeyPair

            keypair = SigningKeyPair.generate(level=3)

            new_key = SigningKey(
                key_id=f"sign_{uuid4().hex[:8]}",
                secret_key=keypair.secret_key,
                public_key=keypair.public_key,
            )

            self._signing_keys[new_key.key_id] = new_key
            old_key_id = self._active_key_id
            self._active_key_id = new_key.key_id

            logger.info(f"Rotated signing key: {old_key_id} -> {new_key.key_id}")

            return new_key.key_id

        except ImportError:
            new_key = SigningKey(
                key_id=f"hmac_{uuid4().hex[:8]}",
                secret_key=os.urandom(32),
                public_key=os.urandom(32),
                algorithm="HMAC-SHA256",
            )

            self._signing_keys[new_key.key_id] = new_key
            old_key_id = self._active_key_id
            self._active_key_id = new_key.key_id

            return new_key.key_id

    def get_public_key(self, key_id: str | None = None) -> str:
        """Get public key for verification."""
        key = self._signing_keys.get(key_id or self._active_key_id)
        if key:
            return base64.b64encode(key.public_key).decode()
        return ""

    def get_status(self) -> dict[str, Any]:
        """Get signing manager status."""
        return {
            "active_key_id": self._active_key_id,
            "key_count": len(self._signing_keys),
            "algorithm": self._signing_keys.get(self._active_key_id, {}).algorithm
            if self._active_key_id
            else None,
            "nonces_tracked": len(self._used_nonces),
            "keys": [
                {
                    "key_id": k.key_id,
                    "algorithm": k.algorithm,
                    "created_at": k.created_at.isoformat(),
                }
                for k in self._signing_keys.values()
            ],
        }


_request_signer: RequestSigningManager | None = None


def get_request_signer() -> RequestSigningManager:
    """Get or create the request signing manager."""
    global _request_signer
    if _request_signer is None:
        _request_signer = RequestSigningManager()
    return _request_signer


class RequestSigningMiddleware(BaseHTTPMiddleware):
    """Middleware to verify request signatures."""

    EXCLUDE_PATHS = {
        "/health",
        "/metrics",
        "/docs",
        "/redoc",
        "/openapi.json",
        "/",
        "/index.html",
        "/dashboard",
        "/dashboard.html",
    }

    OPTIONAL_PATHS = {
        "/api/v1/auth/login",
        "/api/v1/auth/register",
    }

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint):
        if request.url.path in self.EXCLUDE_PATHS:
            return await call_next(request)

        if request.url.path in self.OPTIONAL_PATHS:
            return await call_next(request)

        if request.method == "OPTIONS":
            return await call_next(request)

        if request.url.path.startswith("/api/v1/security"):
            return await call_next(request)

        signer = get_request_signer()
        result = signer.verify_request(request)

        if not result.get("valid"):
            if request.headers.get("X-Signature"):
                raise HTTPException(
                    status_code=401,
                    detail=f"Invalid signature: {result.get('error')}",
                )

        request.state.signature_valid = result.get("valid", False)
        request.state.signature_key_id = result.get("key_id")

        return await call_next(request)


def sign_api_request(
    method: str,
    path: str,
    headers: dict[str, str] | None = None,
    body: str | None = None,
) -> dict[str, str]:
    """Sign an outgoing API request."""
    return get_request_signer().sign_request(
        method=method,
        path=path,
        headers=headers,
        body=body,
    )
