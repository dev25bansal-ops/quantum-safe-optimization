"""
Database abstraction layer with fallback to in-memory storage.

Provides a unified interface for database operations that gracefully
falls back to in-memory storage when Cosmos DB is unavailable.

Usage:
    from api.db.repository import get_job_store, get_user_store, get_key_store

    # In your endpoint:
    job_store = await get_job_store()
    job = await job_store.get(job_id, user_id)
"""

import logging
import uuid
from abc import ABC, abstractmethod
from datetime import UTC, datetime
from typing import Any, Generic, TypeVar

logger = logging.getLogger(__name__)

# Type for stored items
T = TypeVar("T", bound=dict[str, Any])


class BaseStore(ABC, Generic[T]):
    """Abstract base class for data stores."""

    @abstractmethod
    async def create(self, data: T) -> T:
        """Create a new item."""
        pass

    @abstractmethod
    async def get(self, item_id: str, partition_key: str) -> T | None:
        """Get an item by ID."""
        pass

    @abstractmethod
    async def update(self, data: T) -> T:
        """Update an existing item."""
        pass

    @abstractmethod
    async def delete(self, item_id: str, partition_key: str) -> bool:
        """Delete an item."""
        pass

    @abstractmethod
    async def list(
        self,
        partition_key: str,
        filters: dict[str, Any] | None = None,
        limit: int = 20,
        offset: int = 0,
    ) -> list[T]:
        """List items with optional filters."""
        pass

    @abstractmethod
    async def count(
        self,
        partition_key: str,
        filters: dict[str, Any] | None = None,
    ) -> int:
        """Count items with optional filters."""
        pass


class InMemoryJobStore(BaseStore[dict[str, Any]]):
    """In-memory implementation of job store."""

    def __init__(self):
        self._data: dict[str, dict[str, Any]] = {}
        self._partition_counts: dict[str, int] = {}
        self._filtered_counts: dict[str, int] = {}
        self._initialized = True

    @property
    def is_cosmos(self) -> bool:
        return False

    async def create(self, data: dict[str, Any]) -> dict[str, Any]:
        job_id = data.get("job_id") or data.get("id") or str(uuid.uuid4())
        data["id"] = job_id
        data["job_id"] = job_id
        self._data[job_id] = data
        
        # Update partition counter
        user_id = data.get("user_id")
        if user_id:
            self._partition_counts[user_id] = self._partition_counts.get(user_id, 0) + 1
        
        return data

    async def get(self, item_id: str, partition_key: str) -> dict[str, Any] | None:
        job = self._data.get(item_id)
        if job and job.get("user_id") == partition_key:
            return job
        return None

    async def get_any_partition(self, item_id: str) -> dict[str, Any] | None:
        """Get job by ID without requiring partition key."""
        return self._data.get(item_id)

    async def update(self, data: dict[str, Any]) -> dict[str, Any]:
        job_id = data.get("job_id") or data.get("id")
        if job_id in self._data:
            self._data[job_id] = data
        return data

    async def upsert(self, data: dict[str, Any]) -> dict[str, Any]:
        """Create or update."""
        job_id = data.get("job_id") or data.get("id")
        is_new = job_id not in self._data
        
        data["id"] = job_id
        data["job_id"] = job_id
        self._data[job_id] = data
        
        # Update partition counter if new job
        if is_new:
            user_id = data.get("user_id")
            if user_id:
                self._partition_counts[user_id] = self._partition_counts.get(user_id, 0) + 1
        
        return data

    async def delete(self, item_id: str, partition_key: str) -> bool:
        if item_id in self._data:
            job = self._data[item_id]
            if job.get("user_id") == partition_key:
                del self._data[item_id]
                
                # Update partition counter
                self._partition_counts[partition_key] = max(0, self._partition_counts.get(partition_key, 0) - 1)
                
                # Clear filtered counts cache
                self._filtered_counts.clear()
                
                return True
        return False

    async def list(
        self,
        partition_key: str,
        filters: dict[str, Any] | None = None,
        limit: int = 20,
        offset: int = 0,
    ) -> list[dict[str, Any]]:
        # Filter by user_id
        items = [
            j
            for j in self._data.values()
            if j.get("user_id") == partition_key and not j.get("deleted")
        ]

        # Apply additional filters
        if filters:
            if "status" in filters and filters["status"]:
                items = [j for j in items if j.get("status") == filters["status"]]
            if "problem_type" in filters and filters["problem_type"]:
                items = [j for j in items if j.get("problem_type") == filters["problem_type"]]

        # Sort by created_at descending
        items.sort(key=lambda x: x.get("created_at", ""), reverse=True)

        # Paginate
        return items[offset : offset + limit]

    async def count(
        self,
        partition_key: str,
        filters: dict[str, Any] | None = None,
    ) -> int:
        # If no filters, use cached partition count
        if not filters:
            return self._partition_counts.get(partition_key, 0)
        
        # For filtered counts, use cache key
        cache_key = f"{partition_key}:{str(sorted(filters.items()))}"
        if cache_key in self._filtered_counts:
            return self._filtered_counts[cache_key]
        
        # Calculate filtered count
        items = [
            j
            for j in self._data.values()
            if j.get("user_id") == partition_key and not j.get("deleted")
        ]
        
        # Apply filters
        if "status" in filters and filters["status"]:
            items = [j for j in items if j.get("status") == filters["status"]]
        if "problem_type" in filters and filters["problem_type"]:
            items = [j for j in items if j.get("problem_type") == filters["problem_type"]]
        
        count = len(items)
        self._filtered_counts[cache_key] = count
        return count


class InMemoryUserStore(BaseStore[dict[str, Any]]):
    """In-memory implementation of user store."""

    def __init__(self):
        # Pre-populate with admin user
        self._data: dict[str, dict[str, Any]] = {
            "usr_001": {
                "id": "usr_001",
                "user_id": "usr_001",
                "username": "admin",
                "password_hash": "$argon2id$v=19$m=65536,t=3,p=4$RicoB40mT5DxZGqpPral7w$JLxZvZ/PbHdGVitr3eu9RW9danm83u2OADLV5rwNoAw",
                "email": "admin@example.com",
                "roles": ["admin", "user"],
                "created_at": datetime.now(UTC).isoformat(),
                "kem_public_key": None,
            }
        }
        self._username_index: dict[str, str] = {"admin": "usr_001"}
        self._initialized = True

    @property
    def is_cosmos(self) -> bool:
        return False

    async def create(self, data: dict[str, Any]) -> dict[str, Any]:
        user_id = data.get("user_id") or data.get("id") or f"usr_{uuid.uuid4().hex[:8]}"
        data["id"] = user_id
        data["user_id"] = user_id
        self._data[user_id] = data
        if "username" in data:
            self._username_index[data["username"]] = user_id
        return data

    async def get(self, item_id: str, partition_key: str) -> dict[str, Any] | None:
        return self._data.get(item_id)

    async def get_by_username(self, username: str) -> dict[str, Any] | None:
        """Get user by username."""
        user_id = self._username_index.get(username)
        if user_id:
            return self._data.get(user_id)
        return None

    async def update(self, data: dict[str, Any]) -> dict[str, Any]:
        user_id = data.get("user_id") or data.get("id")
        if user_id in self._data:
            # Get old username from existing record (may differ from data)
            old_user = self._data[user_id]
            old_user.get("username") if old_user is not data else None
            new_username = data.get("username")

            # Update the data
            self._data[user_id] = data

            # Update username index if changed
            # Check if old username exists in index pointing to this user
            for uname, uid in list(self._username_index.items()):
                if uid == user_id and uname != new_username:
                    del self._username_index[uname]

            # Add new username to index
            if new_username:
                self._username_index[new_username] = user_id
        return data

    async def upsert(self, data: dict[str, Any]) -> dict[str, Any]:
        """Create or update."""
        user_id = data.get("user_id") or data.get("id")
        if user_id:
            data["id"] = user_id
            self._data[user_id] = data
            if "username" in data:
                self._username_index[data["username"]] = user_id
        return data

    async def delete(self, item_id: str, partition_key: str) -> bool:
        if item_id in self._data:
            user = self._data[item_id]
            if user.get("username") in self._username_index:
                del self._username_index[user["username"]]
            del self._data[item_id]
            return True
        return False

    async def list(
        self,
        partition_key: str = None,  # Ignored for users
        filters: dict[str, Any] | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[dict[str, Any]]:
        items = list(self._data.values())
        items.sort(key=lambda x: x.get("created_at", ""), reverse=True)
        return items[offset : offset + limit]

    async def count(
        self,
        partition_key: str = None,
        filters: dict[str, Any] | None = None,
    ) -> int:
        return len(self._data)


class InMemoryKeyStore(BaseStore[dict[str, Any]]):
    """In-memory implementation of key store."""

    def __init__(self):
        self._data: dict[str, dict[str, Any]] = {}
        self._initialized = True

    @property
    def is_cosmos(self) -> bool:
        return False

    async def create(self, data: dict[str, Any]) -> dict[str, Any]:
        key_id = data.get("key_id") or data.get("id") or f"key_{uuid.uuid4().hex[:16]}"
        data["id"] = key_id
        data["key_id"] = key_id
        self._data[key_id] = data
        return data

    async def get(self, item_id: str, partition_key: str) -> dict[str, Any] | None:
        key = self._data.get(item_id)
        if key and key.get("user_id") == partition_key:
            return key
        return None

    async def get_by_user(self, user_id: str) -> dict[str, Any] | None:
        """Get most recent key for a user."""
        user_keys = [k for k in self._data.values() if k.get("user_id") == user_id]
        if user_keys:
            user_keys.sort(key=lambda x: x.get("created_at", ""), reverse=True)
            return user_keys[0]
        return None

    async def update(self, data: dict[str, Any]) -> dict[str, Any]:
        key_id = data.get("key_id") or data.get("id")
        if key_id in self._data:
            self._data[key_id] = data
        return data

    async def upsert(self, data: dict[str, Any]) -> dict[str, Any]:
        """Create or update."""
        key_id = data.get("key_id") or data.get("id") or f"key_{uuid.uuid4().hex[:16]}"
        data["id"] = key_id
        data["key_id"] = key_id
        self._data[key_id] = data
        return data

    async def delete(self, item_id: str, partition_key: str) -> bool:
        if item_id in self._data:
            key = self._data[item_id]
            if key.get("user_id") == partition_key:
                del self._data[item_id]
                return True
        return False

    async def list(
        self,
        partition_key: str,
        filters: dict[str, Any] | None = None,
        limit: int = 20,
        offset: int = 0,
    ) -> list[dict[str, Any]]:
        items = [k for k in self._data.values() if k.get("user_id") == partition_key]
        items.sort(key=lambda x: x.get("created_at", ""), reverse=True)
        return items[offset : offset + limit]

    async def count(
        self,
        partition_key: str,
        filters: dict[str, Any] | None = None,
    ) -> int:
        return len([k for k in self._data.values() if k.get("user_id") == partition_key])


class InMemoryTokenStore(BaseStore[dict[str, Any]]):
    """In-memory implementation of token store."""

    def __init__(self):
        self._data: dict[str, dict[str, Any]] = {}
        self._initialized = True

    @property
    def is_cosmos(self) -> bool:
        return False

    async def create(self, data: dict[str, Any]) -> dict[str, Any]:
        token = data.get("token") or data.get("id")
        data["id"] = token
        self._data[token] = data
        return data

    async def get(self, item_id: str, partition_key: str = None) -> dict[str, Any] | None:
        return self._data.get(item_id)

    async def update(self, data: dict[str, Any]) -> dict[str, Any]:
        token = data.get("token") or data.get("id")
        if token in self._data:
            self._data[token] = data
        return data

    async def delete(self, item_id: str, partition_key: str = None) -> bool:
        if item_id in self._data:
            del self._data[item_id]
            return True
        return False

    async def list(
        self,
        partition_key: str = None,
        filters: dict[str, Any] | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[dict[str, Any]]:
        items = list(self._data.values())
        return items[offset : offset + limit]

    async def count(
        self,
        partition_key: str = None,
        filters: dict[str, Any] | None = None,
    ) -> int:
        return len(self._data)


class CosmosJobStore(BaseStore[dict[str, Any]]):
    """Cosmos DB implementation of job store."""

    def __init__(self, repository):
        from api.db.cosmos import JobRepository

        self._repo: JobRepository = repository
        self._initialized = True

    @property
    def is_cosmos(self) -> bool:
        return True

    async def create(self, data: dict[str, Any]) -> dict[str, Any]:
        return await self._repo.create_job(data)

    async def get(self, item_id: str, partition_key: str) -> dict[str, Any] | None:
        return await self._repo.get_job(item_id, partition_key)

    async def get_any_partition(self, item_id: str) -> dict[str, Any] | None:
        """Get job by ID without requiring partition key."""
        return await self._repo.get_job_any_user(item_id)

    async def update(self, data: dict[str, Any]) -> dict[str, Any]:
        return await self._repo.update_job(data)

    async def upsert(self, data: dict[str, Any]) -> dict[str, Any]:
        return await self._repo.upsert_job(data)

    async def delete(self, item_id: str, partition_key: str) -> bool:
        return await self._repo.delete_job(item_id, partition_key)

    async def list(
        self,
        partition_key: str,
        filters: dict[str, Any] | None = None,
        limit: int = 20,
        offset: int = 0,
    ) -> list[dict[str, Any]]:
        status = filters.get("status") if filters else None
        problem_type = filters.get("problem_type") if filters else None
        return await self._repo.list_jobs(partition_key, status, problem_type, limit, offset)

    async def count(
        self,
        partition_key: str,
        filters: dict[str, Any] | None = None,
    ) -> int:
        status = filters.get("status") if filters else None
        problem_type = filters.get("problem_type") if filters else None
        return await self._repo.count_jobs(partition_key, status, problem_type)


class CosmosUserStore(BaseStore[dict[str, Any]]):
    """Cosmos DB implementation of user store."""

    def __init__(self, repository):
        from api.db.cosmos import UserRepository

        self._repo: UserRepository = repository
        self._initialized = True

    @property
    def is_cosmos(self) -> bool:
        return True

    async def create(self, data: dict[str, Any]) -> dict[str, Any]:
        return await self._repo.create_user(data)

    async def get(self, item_id: str, partition_key: str) -> dict[str, Any] | None:
        return await self._repo.get_user(item_id)

    async def get_by_username(self, username: str) -> dict[str, Any] | None:
        return await self._repo.get_user_by_username(username)

    async def update(self, data: dict[str, Any]) -> dict[str, Any]:
        return await self._repo.update_user(data)

    async def upsert(self, data: dict[str, Any]) -> dict[str, Any]:
        return await self._repo.upsert_user(data)

    async def delete(self, item_id: str, partition_key: str) -> bool:
        return await self._repo.delete_user(item_id)

    async def list(
        self,
        partition_key: str = None,
        filters: dict[str, Any] | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[dict[str, Any]]:
        return await self._repo.list_users(limit, offset)

    async def count(
        self,
        partition_key: str = None,
        filters: dict[str, Any] | None = None,
    ) -> int:
        return await self._repo.count_users()


class CosmosKeyStore(BaseStore[dict[str, Any]]):
    """Cosmos DB implementation of key store."""

    def __init__(self, repository):
        from api.db.cosmos import KeyRepository

        self._repo: KeyRepository = repository
        self._initialized = True

    @property
    def is_cosmos(self) -> bool:
        return True

    async def create(self, data: dict[str, Any]) -> dict[str, Any]:
        return await self._repo.store_keys(data["user_id"], data)

    async def get(self, item_id: str, partition_key: str) -> dict[str, Any] | None:
        return await self._repo.get_keys(partition_key)

    async def get_by_user(self, user_id: str) -> dict[str, Any] | None:
        return await self._repo.get_keys(user_id)

    async def update(self, data: dict[str, Any]) -> dict[str, Any]:
        return await self._repo.store_keys(data["user_id"], data)

    async def upsert(self, data: dict[str, Any]) -> dict[str, Any]:
        return await self._repo.store_keys(data["user_id"], data)

    async def delete(self, item_id: str, partition_key: str) -> bool:
        # Key deletion not typically needed
        return True

    async def list(
        self,
        partition_key: str,
        filters: dict[str, Any] | None = None,
        limit: int = 20,
        offset: int = 0,
    ) -> list[dict[str, Any]]:
        key = await self.get_by_user(partition_key)
        return [key] if key else []

    async def count(
        self,
        partition_key: str,
        filters: dict[str, Any] | None = None,
    ) -> int:
        key = await self.get_by_user(partition_key)
        return 1 if key else 0


# Global store instances
_job_store: BaseStore | None = None
_user_store: BaseStore | None = None
_key_store: BaseStore | None = None
_token_store: BaseStore | None = None
_cosmos_initialized: bool = False


async def _try_init_cosmos() -> bool:
    """Try to initialize Cosmos DB connection."""
    global _cosmos_initialized

    if _cosmos_initialized:
        return True

    try:
        from api.db.cosmos import cosmos_manager

        if cosmos_manager._initialized:
            _cosmos_initialized = True
            return True
    except Exception as e:
        logger.debug(f"Cosmos DB not available: {e}")

    return False


async def get_job_store() -> BaseStore[dict[str, Any]]:
    """Get the job store (Cosmos DB or in-memory fallback)."""
    global _job_store

    if _job_store is not None:
        return _job_store

    if await _try_init_cosmos():
        try:
            from api.db.cosmos import JobRepository, cosmos_manager

            repo = JobRepository(cosmos_manager)
            _job_store = CosmosJobStore(repo)
            logger.info("Using Cosmos DB for job storage")
            return _job_store
        except Exception as e:
            logger.warning(f"Failed to create Cosmos job store: {e}")

    # Fallback to in-memory
    _job_store = InMemoryJobStore()
    logger.info("Using in-memory storage for jobs (Cosmos DB unavailable)")
    return _job_store


async def get_user_store() -> BaseStore[dict[str, Any]]:
    """Get the user store (Cosmos DB or in-memory fallback)."""
    global _user_store

    if _user_store is not None:
        return _user_store

    if await _try_init_cosmos():
        try:
            from api.db.cosmos import UserRepository, cosmos_manager

            repo = UserRepository(cosmos_manager)
            _user_store = CosmosUserStore(repo)
            logger.info("Using Cosmos DB for user storage")
            return _user_store
        except Exception as e:
            logger.warning(f"Failed to create Cosmos user store: {e}")

    # Fallback to in-memory
    _user_store = InMemoryUserStore()
    logger.info("Using in-memory storage for users (Cosmos DB unavailable)")
    return _user_store


async def get_key_store() -> BaseStore[dict[str, Any]]:
    """Get the key store (Cosmos DB or in-memory fallback)."""
    global _key_store

    if _key_store is not None:
        return _key_store

    if await _try_init_cosmos():
        try:
            from api.db.cosmos import KeyRepository, cosmos_manager

            repo = KeyRepository(cosmos_manager)
            _key_store = CosmosKeyStore(repo)
            logger.info("Using Cosmos DB for key storage")
            return _key_store
        except Exception as e:
            logger.warning(f"Failed to create Cosmos key store: {e}")

    # Fallback to in-memory
    _key_store = InMemoryKeyStore()
    logger.info("Using in-memory storage for keys (Cosmos DB unavailable)")
    return _key_store


async def get_token_store() -> BaseStore[dict[str, Any]]:
    """Get the token store (always in-memory for now)."""
    global _token_store

    if _token_store is not None:
        return _token_store

    # Tokens are typically short-lived and can use in-memory storage
    _token_store = InMemoryTokenStore()
    return _token_store


def reset_stores():
    """Reset all stores (for testing)."""
    global _job_store, _user_store, _key_store, _token_store, _cosmos_initialized
    _job_store = None
    _user_store = None
    _key_store = None
    _token_store = None
    _cosmos_initialized = False

    # Also reset AuthStores singleton
    try:
        from api.auth_stores import AuthStores

        AuthStores.reset()
    except ImportError:
        pass
