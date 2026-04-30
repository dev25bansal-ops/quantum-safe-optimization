"""
Token Revocation Service.

Implements immediate token invalidation for logout and security events.
"""

import asyncio
import hashlib
import json
import os
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from typing import Optional
from uuid import uuid4

import structlog

logger = structlog.get_logger()


@dataclass
class RevokedToken:
    jti: str
    user_id: str
    revoked_at: datetime
    expires_at: datetime
    reason: str = "logout"

    def to_dict(self) -> dict:
        return {
            "jti": self.jti,
            "user_id": self.user_id,
            "revoked_at": self.revoked_at.isoformat(),
            "expires_at": self.expires_at.isoformat(),
            "reason": self.reason,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "RevokedToken":
        return cls(
            jti=data["jti"],
            user_id=data["user_id"],
            revoked_at=datetime.fromisoformat(data["revoked_at"]),
            expires_at=datetime.fromisoformat(data["expires_at"]),
            reason=data.get("reason", "logout"),
        )


class TokenRevocationStore:
    """Thread-safe token revocation store with automatic cleanup."""

    def __init__(self, cleanup_interval_seconds: int = 300):
        self._revoked_tokens: dict[str, RevokedToken] = {}
        self._user_tokens: dict[str, set[str]] = {}
        self._lock = asyncio.Lock()
        self._cleanup_interval = cleanup_interval_seconds
        self._cleanup_task: Optional[asyncio.Task] = None

    async def start_cleanup_task(self) -> None:
        """Start background cleanup task."""
        if self._cleanup_task is None or self._cleanup_task.done():
            self._cleanup_task = asyncio.create_task(self._cleanup_loop())
            logger.info("token_revocation_cleanup_started")

    async def stop_cleanup_task(self) -> None:
        """Stop background cleanup task."""
        if self._cleanup_task and not self._cleanup_task.done():
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass
            logger.info("token_revocation_cleanup_stopped")

    async def _cleanup_loop(self) -> None:
        """Periodically clean up expired tokens."""
        while True:
            try:
                await asyncio.sleep(self._cleanup_interval)
                await self.cleanup_expired()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("cleanup_error", error=str(e))

    async def revoke_token(
        self,
        jti: str,
        user_id: str,
        expires_at: datetime,
        reason: str = "logout",
    ) -> None:
        """Revoke a token by its JTI."""
        async with self._lock:
            revoked_token = RevokedToken(
                jti=jti,
                user_id=user_id,
                revoked_at=datetime.now(timezone.utc),
                expires_at=expires_at,
                reason=reason,
            )

            self._revoked_tokens[jti] = revoked_token

            if user_id not in self._user_tokens:
                self._user_tokens[user_id] = set()
            self._user_tokens[user_id].add(jti)

            logger.info(
                "token_revoked",
                jti=jti[:8] + "...",
                user_id=user_id,
                reason=reason,
            )

    async def is_revoked(self, jti: str) -> bool:
        """Check if a token is revoked."""
        async with self._lock:
            return jti in self._revoked_tokens

    async def revoke_all_user_tokens(
        self,
        user_id: str,
        reason: str = "security_event",
    ) -> int:
        """Revoke all tokens for a user."""
        async with self._lock:
            if user_id not in self._user_tokens:
                return 0

            count = 0
            now = datetime.now(timezone.utc)

            for jti in list(self._user_tokens[user_id]):
                if jti in self._revoked_tokens:
                    token = self._revoked_tokens[jti]
                    token.reason = reason
                    count += 1

            logger.warning(
                "all_user_tokens_revoked",
                user_id=user_id,
                count=count,
                reason=reason,
            )

            return count

    async def cleanup_expired(self) -> int:
        """Remove expired tokens from the store."""
        async with self._lock:
            now = datetime.now(timezone.utc)
            expired_jtis = [
                jti for jti, token in self._revoked_tokens.items() if token.expires_at < now
            ]

            for jti in expired_jtis:
                token = self._revoked_tokens.pop(jti, None)
                if token:
                    user_tokens = self._user_tokens.get(token.user_id)
                    if user_tokens:
                        user_tokens.discard(jti)
                        if not user_tokens:
                            del self._user_tokens[token.user_id]

            if expired_jtis:
                logger.info("expired_tokens_cleaned", count=len(expired_jtis))

            return len(expired_jtis)

    async def get_revocation_count(self) -> dict:
        """Get statistics about revoked tokens."""
        async with self._lock:
            now = datetime.now(timezone.utc)

            active = sum(1 for token in self._revoked_tokens.values() if token.expires_at >= now)
            expired = len(self._revoked_tokens) - active

            reasons: dict[str, int] = {}
            for token in self._revoked_tokens.values():
                if token.expires_at >= now:
                    reasons[token.reason] = reasons.get(token.reason, 0) + 1

            return {
                "total_revoked": len(self._revoked_tokens),
                "active_revocations": active,
                "expired_revocations": expired,
                "unique_users": len(self._user_tokens),
                "by_reason": reasons,
            }


_token_revocation_store: Optional[TokenRevocationStore] = None


def get_token_revocation_store() -> TokenRevocationStore:
    """Get the global token revocation store."""
    global _token_revocation_store
    if _token_revocation_store is None:
        _token_revocation_store = TokenRevocationStore()
    return _token_revocation_store


async def init_token_revocation() -> None:
    """Initialize token revocation service."""
    store = get_token_revocation_store()
    await store.start_cleanup_task()
    logger.info("token_revocation_initialized")


async def close_token_revocation() -> None:
    """Shutdown token revocation service."""
    store = get_token_revocation_store()
    await store.stop_cleanup_task()
    logger.info("token_revocation_closed")
