"""
Bounded In-Memory Stores with TTL and LRU Eviction.

Prevents memory exhaustion from unbounded data growth.
Features:
- Maximum size limits with LRU eviction
- TTL-based expiration
- O(1) operations
- Thread-safe for async contexts
"""

import asyncio
import logging
import time
from collections import OrderedDict
from typing import Any, Optional

logger = logging.getLogger(__name__)


class BoundedInMemoryJobStore:
    """
    Job store with bounded size and TTL expiration.
    
    Prevents memory exhaustion by:
    1. Limiting total number of jobs stored
    2. Automatically evicting oldest/least-recently-used jobs
    3. Expiring jobs after configurable TTL
    """
    
    def __init__(
        self,
        max_size: int = 10000,
        default_ttl_seconds: int = 3600,  # 1 hour
        enable_stats: bool = True,
    ):
        """
        Initialize bounded job store.
        
        Args:
            max_size: Maximum number of jobs to store
            default_ttl_seconds: Default TTL for jobs (seconds)
            enable_stats: Enable hit/miss statistics tracking
        """
        self._data: OrderedDict[str, tuple[dict, float]] = OrderedDict()
        # job_id -> (job_data, expires_at_timestamp)
        
        self._max_size = max_size
        self._default_ttl = default_ttl_seconds
        self._enable_stats = enable_stats
        
        # Statistics
        self._hits = 0
        self._misses = 0
        self._evictions = 0
        self._expirations = 0
        
        # Lock for thread safety
        self._lock = asyncio.Lock()
    
    async def get(self, job_id: str) -> dict | None:
        """
        Get job by ID with TTL check.
        
        Args:
            job_id: Job identifier
            
        Returns:
            Job data or None if not found/expired
        """
        async with self._lock:
            if job_id not in self._data:
                self._misses += 1
                return None
            
            job_data, expires_at = self._data[job_id]
            
            # Check TTL
            if time.time() > expires_at:
                # Expired - remove and return None
                del self._data[job_id]
                self._expirations += 1
                self._misses += 1
                logger.debug("job_expired", job_id=job_id)
                return None
            
            # Move to end (most recently used)
            self._data.move_to_end(job_id)
            self._hits += 1
            
            return job_data
    
    async def set(
        self,
        job_id: str,
        job_data: dict,
        ttl: int | None = None,
    ) -> None:
        """
        Store job data with TTL.
        
        Args:
            job_id: Job identifier
            job_data: Job data to store
            ttl: Override default TTL (seconds)
        """
        async with self._lock:
            # Evict expired entries first
            self._evict_expired()
            
            # Calculate expiration time
            expires_at = time.time() + (ttl or self._default_ttl)
            
            # If job exists, update it (will move to end)
            if job_id in self._data:
                self._data[job_id] = (job_data, expires_at)
                self._data.move_to_end(job_id)
                return
            
            # Evict oldest entries if at capacity
            while len(self._data) >= self._max_size:
                self._evict_oldest()
            
            # Add new job
            self._data[job_id] = (job_data, expires_at)
    
    async def update(self, job_id: str, updates: dict) -> bool:
        """
        Update specific fields of a job.
        
        Args:
            job_id: Job identifier
            updates: Fields to update
            
        Returns:
            True if job was updated, False if not found
        """
        async with self._lock:
            if job_id not in self._data:
                return False
            
            job_data, expires_at = self._data[job_id]
            
            # Check TTL
            if time.time() > expires_at:
                del self._data[job_id]
                self._expirations += 1
                return False
            
            # Update fields
            job_data.update(updates)
            self._data[job_id] = (job_data, expires_at)
            self._data.move_to_end(job_id)
            
            return True
    
    async def delete(self, job_id: str) -> bool:
        """
        Delete a job.
        
        Args:
            job_id: Job identifier
            
        Returns:
            True if job was deleted
        """
        async with self._lock:
            if job_id in self._data:
                del self._data[job_id]
                return True
            return False
    
    async def count(self) -> int:
        """
        Get count of non-expired jobs.
        
        Returns:
            Number of active jobs
        """
        async with self._lock:
            # First evict expired
            self._evict_expired()
            return len(self._data)
    
    async def list(
        self,
        limit: int = 100,
        offset: int = 0,
        filter_fn = None,
    ) -> list[dict]:
        """
        List jobs with pagination.
        
        Args:
            limit: Maximum number of jobs to return
            offset: Number of jobs to skip
            filter_fn: Optional filter function
            
        Returns:
            List of job data dictionaries
        """
        async with self._lock:
            # Evict expired first
            self._evict_expired()
            
            # Get all jobs in LRU order (most recent first)
            all_jobs = []
            for job_id, (job_data, expires_at) in reversed(self._data.items()):
                # Apply filter if provided
                if filter_fn and not filter_fn(job_data):
                    continue
                all_jobs.append(job_data)
            
            # Apply pagination
            start = offset
            end = offset + limit
            
            return all_jobs[start:end]
    
    async def get_stats(self) -> dict:
        """
        Get store statistics.
        
        Returns:
            Dictionary with stats
        """
        async with self._lock:
            self._evict_expired()
            
            total_requests = self._hits + self._misses
            hit_rate = self._hits / total_requests if total_requests > 0 else 0.0
            
            return {
                "total_jobs": len(self._data),
                "max_size": self._max_size,
                "utilization_percent": (len(self._data) / self._max_size) * 100,
                "hits": self._hits,
                "misses": self._misses,
                "hit_rate": hit_rate,
                "evictions": self._evictions,
                "expirations": self._expirations,
                "default_ttl_seconds": self._default_ttl,
            }
    
    async def clear(self) -> int:
        """
        Clear all jobs.
        
        Returns:
            Number of jobs cleared
        """
        async with self._lock:
            count = len(self._data)
            self._data.clear()
            logger.info("job_store_cleared", jobs_removed=count)
            return count
    
    def _evict_expired(self):
        """Remove expired jobs. Must be called within lock."""
        now = time.time()
        expired_keys = [
            key for key, (_, expires_at) in self._data.items()
            if now > expires_at
        ]
        
        for key in expired_keys:
            del self._data[key]
            self._expirations += 1
    
    def _evict_oldest(self):
        """Evict oldest (least recently used) job. Must be called within lock."""
        if self._data:
            # popitem(last=False) removes first item (oldest/LRU)
            oldest_key, _ = self._data.popitem(last=False)
            self._evictions += 1
            logger.debug(
                "job_evicted_lru",
                job_id=oldest_key,
                current_size=len(self._data),
                max_size=self._max_size,
            )
    
    async def close(self):
        """Clean up resources."""
        async with self._lock:
            self._data.clear()
            logger.info("job_store_closed")


class BoundedInMemoryUserStore:
    """
    User store with bounded size for session/token caching.
    Note: For production, use Redis/DB instead of in-memory.
    """
    
    def __init__(
        self,
        max_size: int = 5000,
        default_ttl_seconds: int = 86400,  # 24 hours
    ):
        self._data: OrderedDict[str, tuple[dict, float]] = OrderedDict()
        self._max_size = max_size
        self._default_ttl = default_ttl_seconds
        self._lock = asyncio.Lock()
    
    async def get(self, key: str) -> dict | None:
        """Get user/session data with TTL check."""
        async with self._lock:
            if key not in self._data:
                return None
            
            data, expires_at = self._data[key]
            
            if time.time() > expires_at:
                del self._data[key]
                return None
            
            self._data.move_to_end(key)
            return data
    
    async def set(self, key: str, data: dict, ttl: int | None = None) -> None:
        """Store user/session data with TTL."""
        async with self._lock:
            self._evict_expired()
            
            expires_at = time.time() + (ttl or self._default_ttl)
            
            if key in self._data:
                self._data[key] = (data, expires_at)
                self._data.move_to_end(key)
                return
            
            while len(self._data) >= self._max_size:
                self._data.popitem(last=False)
            
            self._data[key] = (data, expires_at)
    
    async def delete(self, key: str) -> bool:
        """Delete user/session data."""
        async with self._lock:
            if key in self._data:
                del self._data[key]
                return True
            return False
    
    def _evict_expired(self):
        """Remove expired entries."""
        now = time.time()
        expired = [k for k, (_, exp) in self._data.items() if now > exp]
        for k in expired:
            del self._data[k]
    
    async def clear(self):
        """Clear all data."""
        async with self._lock:
            self._data.clear()


# Module-level instances for easy import
# These should be injected in production for testability
default_job_store = BoundedInMemoryJobStore(
    max_size=10000,
    default_ttl_seconds=3600,  # 1 hour
)

default_user_store = BoundedInMemoryUserStore(
    max_size=5000,
    default_ttl_seconds=86400,  # 24 hours
)


async def get_job_store() -> BoundedInMemoryJobStore:
    """Get default job store instance."""
    return default_job_store


async def get_user_store() -> BoundedInMemoryUserStore:
    """Get default user store instance."""
    return default_user_store
