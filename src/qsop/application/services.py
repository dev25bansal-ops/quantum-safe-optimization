"""
Domain services for users, jobs, and keys.

Provides clean dependency injection and business logic layer.
"""

import logging
from typing import Any

from qsop.infrastructure.persistence.redis_storage import get_storage

logger = logging.getLogger(__name__)


class UserService:
    """
    Service for user-related operations.

    Provides business logic for user management with dependency injection.
    """

    async def create_user(self, user_data: dict[str, Any]) -> dict[str, Any]:
        """
        Create a new user.

        Args:
            user_data: User data including username, password_hash, etc.

        Returns:
            Created user data

        Raises:
            ValueError: If username already exists
        """
        storage = get_storage()

        # Check if username exists
        existing = await storage.user_get_by_username(user_data["username"])
        if existing:
            raise ValueError(f"Username already exists: {user_data['username']}")

        # Check email uniqueness if provided
        if user_data.get("email"):
            users = await storage.user_list(limit=1000)
            for u in users:
                if u.get("email") == user_data["email"]:
                    raise ValueError(f"Email already registered: {user_data['email']}")

        await storage.user_create(user_data["username"], user_data)
        logger.info(f"Created user: {user_data['username']}")

        return user_data

    async def get_user_by_username(self, username: str) -> dict[str, Any] | None:
        """
        Get user by username.

        Args:
            username: User's username

        Returns:
            User data or None if not found
        """
        storage = get_storage()
        return await storage.user_get_by_username(username)

    async def get_user_by_user_id(self, user_id: str) -> dict[str, Any] | None:
        """
        Get user by user_id.

        Args:
            user_id: User's ID

        Returns:
            User data or None if not found
        """
        storage = get_storage()
        return await storage.user_get_by_user_id(user_id)

    async def update_user_encryption_key(
        self,
        username: str,
        kem_public_key: str,
    ) -> dict[str, Any]:
        """
        Update user's encryption key.

        Args:
            username: User's username
            kem_public_key: ML-KEM public key

        Returns:
            Updated user data

        Raises:
            ValueError: If user not found
        """
        storage = get_storage()
        user = await storage.user_get_by_username(username)

        if not user:
            raise ValueError(f"User not found: {username}")

        user["kem_public_key"] = kem_public_key
        await storage.user_create(username, user)

        logger.info(f"Updated encryption key for user: {username}")
        return user

    async def get_user_public_key(self, user_id: str) -> str | None:
        """
        Get user's ML-KEM public key.

        Args:
            user_id: User's ID

        Returns:
            Public key or None if not found
        """
        user = await self.get_user_by_user_id(user_id)
        return user.get("kem_public_key") if user else None


class JobService:
    """
    Service for job-related operations.

    Provides business logic for job management with dependency injection.
    """

    async def create_job(self, job_data: dict[str, Any]) -> dict[str, Any]:
        """
        Create a new job.

        Args:
            job_data: Job data including user_id, problem_type, etc.

        Returns:
            Created job data
        """
        storage = get_storage()
        await storage.job_create(job_data["job_id"], job_data)
        logger.info(f"Created job: {job_data['job_id']}")
        return job_data

    async def get_job(self, job_id: str) -> dict[str, Any] | None:
        """
        Get job by ID.

        Args:
            job_id: Job ID

        Returns:
            Job data or None if not found
        """
        storage = get_storage()
        return await storage.job_get(job_id)

    async def update_job(self, job_id: str, updates: dict[str, Any]) -> dict[str, Any]:
        """
        Update a job.

        Args:
            job_id: Job ID
            updates: Fields to update

        Returns:
            Updated job data

        Raises:
            ValueError: If job not found
        """
        storage = get_storage()
        job = await storage.job_get(job_id)

        if not job:
            raise ValueError(f"Job not found: {job_id}")

        job.update(updates)
        await storage.job_create(job_id, job)

        logger.debug(f"Updated job: {job_id}")
        return job

    async def delete_job(self, job_id: str, user_id: str) -> bool:
        """
        Delete a job.

        Args:
            job_id: Job ID
            user_id: User ID (for authorization)

        Returns:
            True if deleted

        Raises:
            ValueError: If job not found or user doesn't own it
        """
        storage = get_storage()
        job = await storage.job_get(job_id)

        if not job:
            raise ValueError(f"Job not found: {job_id}")

        if job.get("user_id") != user_id:
            raise ValueError(f"User does not own job: {job_id}")

        result = await storage.job_delete(job_id)
        logger.info(f"Deleted job: {job_id}")
        return result

    async def list_user_jobs(
        self,
        user_id: str,
        status: str | None = None,
        problem_type: str | None = None,
        limit: int = 20,
        offset: int = 0,
    ) -> tuple[list[dict[str, Any]], int]:
        """
        List jobs for a user with filtering and pagination.

        Args:
            user_id: User ID
            status: Optional status filter
            problem_type: Optional problem type filter
            limit: Maximum number of jobs to return
            offset: Number of jobs to skip

        Returns:
            Tuple of (jobs list, total count)
        """
        storage = get_storage()

        filters = {}
        if status:
            filters["status"] = status
        if problem_type:
            filters["problem_type"] = problem_type.upper()

        jobs = await storage.job_list(user_id, filters, limit, offset)
        total = await storage.job_count(user_id, filters)

        return jobs, total

    async def publish_job_update(
        self,
        job_id: str,
        update_type: str,
        data: dict[str, Any],
    ) -> None:
        """
        Publish a job update to Redis pub/sub for WebSocket broadcasting.

        Args:
            job_id: Job ID
            update_type: Type of update (status, progress, error, etc.)
            data: Update data
        """
        storage = get_storage()

        event = {
            "type": update_type,
            "job_id": job_id,
            "timestamp": data.get("timestamp"),
            **data,
        }

        channel = f"job:{job_id}:progress"
        await storage.publish_event(channel, event)


class KeyService:
    """
    Service for encryption key management.

    Provides business logic for key operations with dependency injection.
    """

    async def save_user_keys(
        self,
        user_id: str,
        key_data: dict[str, Any],
    ) -> dict[str, Any]:
        """
        Save or update user's encryption keys.

        Args:
            user_id: User ID
            key_data: Key data including public_key, etc.

        Returns:
            Saved key data
        """
        storage = get_storage()
        key_data["user_id"] = user_id
        await storage.key_create(user_id, key_data)

        logger.info(f"Saved keys for user: {user_id}")
        return key_data

    async def get_user_keys(self, user_id: str) -> dict[str, Any] | None:
        """
        Get user's encryption keys.

        Args:
            user_id: User ID

        Returns:
            Key data or None if not found
        """
        storage = get_storage()
        return await storage.key_get(user_id)


class TokenService:
    """
    Service for token management.

    Provides business logic for token operations with dependency injection.
    """

    async def create_token(
        self,
        token: str,
        token_data: dict[str, Any],
        ttl_seconds: int | None = None,
    ) -> dict[str, Any]:
        """
        Create and store a token.

        Args:
            token: Token string
            token_data: Token data including user_id, jti, etc.
            ttl_seconds: TTL in seconds (default: 24 hours)

        Returns:
            Token data
        """
        storage = get_storage()
        await storage.token_create(token, token_data, ttl_seconds)

        logger.debug(f"Created token for user: {token_data.get('user_id')}")
        return token_data

    async def validate_token(self, token: str) -> dict[str, Any] | None:
        """
        Validate a token by checking it exists and is not revoked.

        Args:
            token: Token string

        Returns:
            Token data or None if invalid
        """
        storage = get_storage()
        return await storage.token_get(token)

    async def revoke_token(self, token: str) -> bool:
        """
        Revoke a token.

        Args:
            token: Token string

        Returns:
            True if revoked
        """
        storage = get_storage()
        result = await storage.token_revoke(token)

        if result:
            logger.info(f"Revoked token: {token[:20]}...")

        return result

    async def revoke_token_by_jti(self, jti: str) -> bool:
        """
        Revoke a token by JTI.

        Args:
            jti: JWT ID

        Returns:
            True if revoked
        """
        storage = get_storage()
        result = await storage.token_revoke_by_jti(jti)

        if result:
            logger.info(f"Revoked token by JTI: {jti}")

        return result

    async def revoke_all_user_tokens(self, user_id: str) -> int:
        """
        Revoke all tokens for a user.

        Args:
            user_id: User ID

        Returns:
            Number of tokens revoked
        """
        storage = get_storage()
        count = await storage.token_revoke_all_for_user(user_id)

        logger.info(f"Revoked {count} tokens for user: {user_id}")
        return count


# Global service instances
_user_service: UserService | None = None
_job_service: JobService | None = None
_key_service: KeyService | None = None
_token_service: TokenService | None = None


def get_user_service() -> UserService:
    """Get global user service instance."""
    global _user_service
    if _user_service is None:
        _user_service = UserService()
    return _user_service


def get_job_service() -> JobService:
    """Get global job service instance."""
    global _job_service
    if _job_service is None:
        _job_service = JobService()
    return _job_service


def get_key_service() -> KeyService:
    """Get global key service instance."""
    global _key_service
    if _key_service is None:
        _key_service = KeyService()
    return _key_service


def get_token_service() -> TokenService:
    """Get global token service instance."""
    global _token_service
    if _token_service is None:
        _token_service = TokenService()
    return _token_service


__all__ = [
    "UserService",
    "JobService",
    "KeyService",
    "TokenService",
    "get_user_service",
    "get_job_service",
    "get_key_service",
    "get_token_service",
]
