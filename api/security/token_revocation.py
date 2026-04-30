"""
Token revocation service using Redis.

Provides secure token blacklisting for logout and security events.
"""

import os
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Optional

import redis.asyncio as redis


@dataclass
class TokenRevocationConfig:
    """Configuration for token revocation service."""

    redis_url: str = os.getenv("REDIS_URL", "redis://localhost:6379")
    key_prefix: str = "revoked_token:"
    default_ttl_hours: int = 24  # Match token expiry
    use_memory_fallback: bool = True  # Fall back to memory if Redis unavailable


class TokenRevocationService:
    """
    Service for managing token revocation with Redis backend.

    Supports:
    - Individual token revocation (logout)
    - Bulk revocation (security events)
    - Automatic expiry cleanup
    - Memory fallback when Redis is unavailable
    """

    _instance: Optional["TokenRevocationService"] = None
    _redis: redis.Redis | None = None
    _memory_blacklist: set[str] = set()  # Fallback storage
    _memory_expiry: dict = {}  # Track expiry times for memory fallback
    _use_memory: bool = False
    _initialized: bool = False

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance.config = TokenRevocationConfig()  # Set default config
        return cls._instance

    async def initialize(self, config: TokenRevocationConfig | None = None):
        """Initialize the revocation service."""
        if self._initialized:
            return

        self.config = config or TokenRevocationConfig()

        try:
            self._redis = redis.from_url(
                self.config.redis_url,
                encoding="utf-8",
                decode_responses=True,
            )
            # Test connection
            await self._redis.ping()
            self._use_memory = False
        except Exception:
            if self.config.use_memory_fallback:
                self._use_memory = True
            else:
                raise

        self._initialized = True

    async def close(self):
        """Close Redis connection."""
        if self._redis:
            await self._redis.close()
            self._redis = None
        self._initialized = False

    def _get_key(self, token_jti: str) -> str:
        """Get Redis key for a token."""
        return f"{self.config.key_prefix}{token_jti}"

    async def revoke_token(
        self,
        token_jti: str,
        reason: str = "logout",
        user_id: str | None = None,
        ttl_seconds: int | None = None,
    ) -> bool:
        """
        Revoke a token by its JTI (JWT ID).

        Args:
            token_jti: The unique token identifier
            reason: Reason for revocation (logout, security, admin)
            user_id: Optional user ID for audit
            ttl_seconds: TTL in seconds (default: 24 hours)

        Returns:
            True if successfully revoked
        """
        ttl = ttl_seconds or (self.config.default_ttl_hours * 3600)
        revocation_data = {
            "revoked_at": datetime.now(UTC).isoformat(),
            "reason": reason,
            "user_id": user_id or "unknown",
        }

        if self._use_memory:
            self._memory_blacklist.add(token_jti)
            self._memory_expiry[token_jti] = datetime.now(UTC) + timedelta(seconds=ttl)
            return True

        try:
            key = self._get_key(token_jti)
            await self._redis.hset(key, mapping=revocation_data)
            await self._redis.expire(key, ttl)
            return True
        except Exception:
            # Fallback to memory
            self._memory_blacklist.add(token_jti)
            return True

    async def is_revoked(self, token_jti: str) -> bool:
        """
        Check if a token has been revoked.

        Args:
            token_jti: The unique token identifier

        Returns:
            True if token is revoked/blacklisted
        """
        if self._use_memory:
            # Clean expired entries
            now = datetime.now(UTC)
            expired = [jti for jti, exp in self._memory_expiry.items() if exp < now]
            for jti in expired:
                self._memory_blacklist.discard(jti)
                del self._memory_expiry[jti]

            return token_jti in self._memory_blacklist

        try:
            key = self._get_key(token_jti)
            exists = await self._redis.exists(key)
            return exists > 0
        except Exception:
            # Check memory fallback
            return token_jti in self._memory_blacklist

    async def revoke_all_user_tokens(self, user_id: str, reason: str = "security") -> int:
        """
        Revoke all tokens for a user (e.g., after password change).

        This requires a separate user->tokens index.
        For now, this is a placeholder for production implementation.

        Returns:
            Number of tokens revoked
        """
        # In production, maintain a set of active JTIs per user
        # and iterate through them to revoke
        user_tokens_key = f"user_tokens:{user_id}"

        if self._use_memory:
            return 0  # Memory fallback doesn't support this

        try:
            tokens = await self._redis.smembers(user_tokens_key)
            count = 0
            for token_jti in tokens:
                if await self.revoke_token(token_jti, reason, user_id):
                    count += 1
            await self._redis.delete(user_tokens_key)
            return count
        except Exception:
            return 0

    async def get_revocation_stats(self) -> dict:
        """Get statistics about revoked tokens."""
        if self._use_memory:
            return {
                "backend": "memory",
                "revoked_count": len(self._memory_blacklist),
                "pending_expiry": len(self._memory_expiry),
            }

        try:
            # Count keys with prefix
            cursor = 0
            count = 0
            while True:
                cursor, keys = await self._redis.scan(
                    cursor, match=f"{self.config.key_prefix}*", count=100
                )
                count += len(keys)
                if cursor == 0:
                    break

            return {
                "backend": "redis",
                "revoked_count": count,
            }
        except Exception as e:
            return {"backend": "error", "error": str(e)}


# Global instance
token_revocation_service = TokenRevocationService()


async def init_token_revocation():
    """Initialize the token revocation service."""
    await token_revocation_service.initialize()


async def close_token_revocation():
    """Close the token revocation service."""
    await token_revocation_service.close()
