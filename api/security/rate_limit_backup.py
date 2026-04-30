"""
Rate Limit Backup Persistence.

Provides fallback storage for rate limit state when Redis is unavailable.
Ensures rate limiting continues to work during Redis outages.
"""

import asyncio
import json
import logging
import os
import time
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

BACKUP_DIR = Path(os.getenv("RATE_LIMIT_BACKUP_DIR", "/tmp/rate_limit_backups"))
BACKUP_INTERVAL_SECONDS = int(os.getenv("RATE_LIMIT_BACKUP_INTERVAL", "60"))
MAX_BACKUP_AGE_HOURS = int(os.getenv("RATE_LIMIT_BACKUP_MAX_AGE", "24"))


@dataclass
class RateLimitEntry:
    """A rate limit entry."""

    key: str
    timestamp: float
    count: int
    ttl_seconds: int
    metadata: dict[str, Any] = field(default_factory=dict)

    def is_expired(self) -> bool:
        return time.time() > (self.timestamp + self.ttl_seconds)

    def to_dict(self) -> dict:
        return {
            "key": self.key,
            "timestamp": self.timestamp,
            "count": self.count,
            "ttl_seconds": self.ttl_seconds,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "RateLimitEntry":
        return cls(
            key=data["key"],
            timestamp=data["timestamp"],
            count=data["count"],
            ttl_seconds=data["ttl_seconds"],
            metadata=data.get("metadata", {}),
        )


class RateLimitBackupStore:
    """
    Backup store for rate limit state.

    Provides:
    - File-based backup of rate limit state
    - Periodic backup scheduling
    - Recovery from backup on startup
    - Cleanup of old backups
    """

    def __init__(self, backup_dir: Path = BACKUP_DIR):
        self.backup_dir = backup_dir
        self.backup_dir.mkdir(parents=True, exist_ok=True)
        self._memory_store: dict[str, list[RateLimitEntry]] = defaultdict(list)
        self._lock = asyncio.Lock()
        self._backup_task: asyncio.Task | None = None
        self._running = False

    async def start_backup_scheduler(self):
        """Start periodic backup task."""
        if self._running:
            return

        self._running = True
        self._backup_task = asyncio.create_task(self._backup_loop())
        logger.info("rate_limit_backup_scheduler_started", interval=BACKUP_INTERVAL_SECONDS)

    async def stop_backup_scheduler(self):
        """Stop backup task."""
        self._running = False
        if self._backup_task:
            self._backup_task.cancel()
            try:
                await self._backup_task
            except asyncio.CancelledError:
                pass
        await self.save_backup()
        logger.info("rate_limit_backup_scheduler_stopped")

    async def _backup_loop(self):
        """Periodic backup loop."""
        while self._running:
            try:
                await asyncio.sleep(BACKUP_INTERVAL_SECONDS)
                await self.save_backup()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("backup_loop_error", error=str(e))

    async def record_hit(
        self,
        key: str,
        count: int = 1,
        ttl_seconds: int = 60,
        metadata: dict[str, Any] | None = None,
    ):
        """Record a rate limit hit."""
        async with self._lock:
            entry = RateLimitEntry(
                key=key,
                timestamp=time.time(),
                count=count,
                ttl_seconds=ttl_seconds,
                metadata=metadata or {},
            )
            self._memory_store[key].append(entry)

            self._memory_store[key] = [e for e in self._memory_store[key] if not e.is_expired()]

    async def get_hit_count(self, key: str, window_seconds: int = 60) -> int:
        """Get hit count for a key within the window."""
        async with self._lock:
            now = time.time()
            window_start = now - window_seconds

            entries = self._memory_store.get(key, [])
            return sum(e.count for e in entries if e.timestamp >= window_start)

    async def save_backup(self):
        """Save current state to backup file."""
        async with self._lock:
            try:
                timestamp = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
                backup_file = self.backup_dir / f"rate_limits_{timestamp}.json"

                data = {
                    "timestamp": time.time(),
                    "entries": {
                        key: [e.to_dict() for e in entries if not e.is_expired()]
                        for key, entries in self._memory_store.items()
                    },
                }

                backup_file.write_text(json.dumps(data, indent=2))
                logger.info("rate_limit_backup_saved", file=str(backup_file))

                await self._cleanup_old_backups()

            except Exception as e:
                logger.error("backup_save_error", error=str(e))

    async def restore_from_backup(self) -> bool:
        """Restore state from the most recent backup."""
        try:
            backup_files = sorted(
                self.backup_dir.glob("rate_limits_*.json"),
                key=lambda f: f.stat().st_mtime,
                reverse=True,
            )

            if not backup_files:
                logger.info("no_backup_files_found")
                return False

            latest_backup = backup_files[0]
            data = json.loads(latest_backup.read_text())

            async with self._lock:
                for key, entries in data.get("entries", {}).items():
                    self._memory_store[key] = [RateLimitEntry.from_dict(e) for e in entries]

            logger.info(
                "rate_limit_backup_restored",
                file=str(latest_backup),
                keys_restored=len(data.get("entries", {})),
            )
            return True

        except Exception as e:
            logger.error("backup_restore_error", error=str(e))
            return False

    async def _cleanup_old_backups(self):
        """Remove backup files older than MAX_BACKUP_AGE_HOURS."""
        try:
            max_age_seconds = MAX_BACKUP_AGE_HOURS * 3600
            now = time.time()

            for backup_file in self.backup_dir.glob("rate_limits_*.json"):
                if now - backup_file.stat().st_mtime > max_age_seconds:
                    backup_file.unlink()
                    logger.info("old_backup_removed", file=str(backup_file))

        except Exception as e:
            logger.error("backup_cleanup_error", error=str(e))

    async def get_stats(self) -> dict[str, Any]:
        """Get backup store statistics."""
        async with self._lock:
            total_entries = sum(len(entries) for entries in self._memory_store.values())
            total_hits = sum(
                sum(e.count for e in entries) for entries in self._memory_store.values()
            )

            backup_files = list(self.backup_dir.glob("rate_limits_*.json"))

            return {
                "keys_tracked": len(self._memory_store),
                "total_entries": total_entries,
                "total_hits": total_hits,
                "backup_files_count": len(backup_files),
                "backup_dir": str(self.backup_dir),
                "scheduler_running": self._running,
            }


backup_store = RateLimitBackupStore()


async def init_backup_store():
    """Initialize the backup store."""
    await backup_store.restore_from_backup()
    await backup_store.start_backup_scheduler()


async def close_backup_store():
    """Close the backup store."""
    await backup_store.stop_backup_scheduler()
