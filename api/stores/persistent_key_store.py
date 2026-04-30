"""
Persistent Key Store for PQC Key Rotation Service.

Stores PQC keys in Redis/database for persistence across restarts.
Replaces the in-memory-only key store.
"""

import json
import logging
from datetime import UTC, datetime
from typing import Any, Optional

logger = logging.getLogger(__name__)


class PersistentKeyStore:
    """
    Persistent storage for PQC keys.
    
    Features:
    - Redis-backed key storage
    - Key metadata persistence
    - Automatic expiration handling
    - Audit trail for key operations
    """
    
    def __init__(self, redis_client=None, key_prefix: str = "pqc:keys"):
        """
        Initialize persistent key store.
        
        Args:
            redis_client: Redis client instance
            key_prefix: Redis key prefix
        """
        self.redis = redis_client
        self.key_prefix = key_prefix
    
    async def save_key(self, key_id: str, key_data: dict) -> bool:
        """
        Save key to persistent storage.
        
        Args:
            key_id: Unique key identifier
            key_data: Key data and metadata
            
        Returns:
            True if saved successfully
        """
        if not self.redis:
            logger.warning("persistent_key_store_unavailable")
            return False
        
        try:
            key = f"{self.key_prefix}:{key_id}"
            serialized = json.dumps(key_data, default=str)
            
            # Set with TTL based on expiry
            ttl = None
            if "expires_at" in key_data:
                expires_at = datetime.fromisoformat(key_data["expires_at"])
                ttl = int((expires_at - datetime.now(UTC)).total_seconds())
                if ttl > 0:
                    await self.redis.set(key, serialized, ex=ttl)
                else:
                    # Already expired, don't save
                    return False
            else:
                await self.redis.set(key, serialized)
            
            # Update index
            await self._update_key_index(key_id, key_data)
            
            logger.debug("key_saved_persistent", key_id=key_id)
            return True
            
        except Exception as e:
            logger.error("key_save_failed", error=str(e), key_id=key_id)
            return False
    
    async def load_key(self, key_id: str) -> dict | None:
        """
        Load key from persistent storage.
        
        Args:
            key_id: Key identifier
            
        Returns:
            Key data or None if not found
        """
        if not self.redis:
            return None
        
        try:
            key = f"{self.key_prefix}:{key_id}"
            serialized = await self.redis.get(key)
            
            if serialized:
                return json.loads(serialized)
            
            return None
            
        except Exception as e:
            logger.error("key_load_failed", error=str(e), key_id=key_id)
            return None
    
    async def delete_key(self, key_id: str) -> bool:
        """
        Delete key from persistent storage.
        
        Args:
            key_id: Key identifier
            
        Returns:
            True if deleted
        """
        if not self.redis:
            return False
        
        try:
            key = f"{self.key_prefix}:{key_id}"
            await self.redis.delete(key)
            
            # Remove from index
            await self._remove_from_index(key_id)
            
            logger.debug("key_deleted_persistent", key_id=key_id)
            return True
            
        except Exception as e:
            logger.error("key_delete_failed", error=str(e), key_id=key_id)
            return False
    
    async def list_active_keys(self, key_type: str = None) -> list[dict]:
        """
        List all active (non-expired) keys.
        
        Args:
            key_type: Optional filter by key type
            
        Returns:
            List of key data dictionaries
        """
        if not self.redis:
            return []
        
        try:
            # Get index
            index_key = f"{self.key_prefix}:index"
            key_ids = await self.redis.smembers(index_key)
            
            keys = []
            for key_id in key_ids:
                key_data = await self.load_key(key_id)
                if key_data and key_data.get("is_active"):
                    # Check if expired
                    if "expires_at" in key_data:
                        expires_at = datetime.fromisoformat(key_data["expires_at"])
                        if datetime.now(UTC) > expires_at:
                            continue  # Skip expired keys
                    
                    # Filter by type if specified
                    if key_type and key_data.get("key_type") != key_type:
                        continue
                    
                    keys.append(key_data)
            
            return keys
            
        except Exception as e:
            logger.error("key_list_failed", error=str(e))
            return []
    
    async def record_key_operation(self, key_id: str, operation: str, details: dict = None) -> bool:
        """
        Record key operation for audit trail.
        
        Args:
            key_id: Key identifier
            operation: Operation type (rotate, create, delete)
            details: Additional operation details
            
        Returns:
            True if recorded
        """
        if not self.redis:
            return False
        
        try:
            audit_key = f"{self.key_prefix}:audit:{key_id}"
            audit_entry = {
                "timestamp": datetime.now(UTC).isoformat(),
                "operation": operation,
                "details": details or {},
            }
            
            # Append to list
            await self.redis.lpush(audit_key, json.dumps(audit_entry, default=str))
            
            # Keep only last 100 entries
            await self.redis.ltrim(audit_key, 0, 99)
            
            # Set expiry (1 year)
            await self.redis.expire(audit_key, 31536000)
            
            return True
            
        except Exception as e:
            logger.error("audit_record_failed", error=str(e))
            return False
    
    async def _update_key_index(self, key_id: str, key_data: dict):
        """Update key index for listing."""
        if not self.redis:
            return
        
        try:
            index_key = f"{self.key_prefix}:index"
            await self.redis.sadd(index_key, key_id)
        except Exception as e:
            logger.warning("key_index_update_failed", error=str(e))
    
    async def _remove_from_index(self, key_id: str):
        """Remove key from index."""
        if not self.redis:
            return
        
        try:
            index_key = f"{self.key_prefix}:index"
            await self.redis.srem(index_key, key_id)
        except Exception as e:
            logger.warning("key_index_removal_failed", error=str(e))


async def init_persistent_key_store(redis_url: str = None) -> PersistentKeyStore:
    """
    Initialize persistent key store from Redis URL.
    
    Args:
        redis_url: Redis connection URL
        
    Returns:
        Configured PersistentKeyStore instance
    """
    if not redis_url:
        logger.warning("persistent_key_store_no_redis_url")
        return PersistentKeyStore()  # No-op store
    
    try:
        import redis.asyncio as redis
        redis_client = redis.from_url(redis_url, decode_responses=True)
        await redis_client.ping()
        
        store = PersistentKeyStore(redis_client=redis_client)
        logger.info("persistent_key_store_initialized")
        return store
        
    except Exception as e:
        logger.error("persistent_key_store_init_failed", error=str(e))
        return PersistentKeyStore()  # No-op store
