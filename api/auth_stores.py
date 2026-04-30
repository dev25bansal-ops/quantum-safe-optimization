"""
Authentication stores with dependency injection support.

Provides both in-memory and database-backed storage for users, tokens, and keys.
"""

import logging
import os
import secrets
from datetime import UTC, datetime
from typing import Protocol

from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError

logger = logging.getLogger(__name__)

_password_hasher = PasswordHasher()


class UserStore(Protocol):
    """Protocol for user storage."""

    async def get_by_username(self, username: str) -> dict | None: ...
    async def get_by_id(self, user_id: str) -> dict | None: ...
    async def save(self, user: dict) -> dict: ...
    async def list(self, limit: int = 100) -> list[dict]: ...


class TokenStore(Protocol):
    """Protocol for token storage."""

    async def save(self, token: dict) -> None: ...
    async def get(self, token_id: str) -> dict | None: ...
    async def delete(self, token_id: str) -> None: ...
    async def revoke(self, token_id: str, reason: str) -> None: ...


class KeyStore(Protocol):
    """Protocol for key storage."""

    async def save(self, key: dict) -> None: ...
    async def get(self, key_id: str) -> dict | None: ...
    async def list_for_user(self, user_id: str) -> list[dict]: ...


class InMemoryUserStore:
    """In-memory user storage (for development/testing) with optimized indexes."""

    def __init__(self):
        self._users: dict[str, dict] = {}
        self._email_index: dict[str, str] = {}  # email -> user_id (O(1) lookup)
        self._id_index: dict[str, str] = {}  # user_id -> username (O(1) lookup)
        self._initialize_default_admin()

    def _initialize_default_admin(self) -> None:
        """Initialize default admin user from environment variables."""
        admin_username = os.environ.get("ADMIN_USERNAME", "admin")
        admin_password = os.environ.get("ADMIN_PASSWORD")

        app_env = os.environ.get("APP_ENV", "development")

        if app_env == "production" and not admin_password:
            raise RuntimeError(
                "SECURITY CRITICAL: ADMIN_PASSWORD environment variable must be set in production. "
                "Refusing to start with insecure configuration."
            )

        if not admin_password:
            # Generate a random password for development instead of using 'changeme'
            import secrets
            admin_password = secrets.token_urlsafe(16)
            logger.warning(
                f"SECURITY: Generated random admin password: {admin_password}. "
                "Save it now! Set ADMIN_PASSWORD environment variable for persistence."
            )

        if admin_username not in self._users:
            admin_user = {
                "user_id": "usr_001",
                "id": "usr_001",
                "username": admin_username,
                "password_hash": _password_hasher.hash(admin_password),
                "email": os.environ.get("ADMIN_EMAIL", "admin@example.com"),
                "roles": ["admin", "user"],
                "created_at": datetime.now(UTC).isoformat(),
                "kem_public_key": None,
            }
            self._users[admin_username] = admin_user
            
            # Build indexes
            if admin_user.get("email"):
                self._email_index[admin_user["email"]] = admin_user["user_id"]
            self._id_index[admin_user["user_id"]] = admin_username
            
            logger.info(f"Initialized admin user: {admin_username}")

    async def get_by_username(self, username: str) -> dict | None:
        return self._users.get(username)

    async def get_by_id(self, user_id: str) -> dict | None:
        # O(1) lookup via index instead of O(n) iteration
        username = self._id_index.get(user_id)
        if username:
            return self._users.get(username)
        return None

    async def get_by_email(self, email: str) -> dict | None:
        """Get user by email using index (O(1))."""
        user_id = self._email_index.get(email)
        if user_id:
            username = self._id_index.get(user_id)
            if username:
                return self._users.get(username)
        return None

    async def email_exists(self, email: str) -> bool:
        """Check if email exists using index (O(1) instead of O(n))."""
        return email in self._email_index

    async def save(self, user: dict) -> dict:
        username = user.get("username")
        if username:
            # Remove old email index if updating existing user
            old_user = self._users.get(username)
            if old_user and old_user.get("email"):
                self._email_index.pop(old_user["email"], None)
            
            self._users[username] = user
            
            # Update indexes
            if user.get("email"):
                self._email_index[user["email"]] = user.get("user_id", "")
            if user.get("user_id"):
                self._id_index[user["user_id"]] = username
                
        return user

    async def delete(self, username: str) -> bool:
        """Delete user and remove from indexes."""
        if username in self._users:
            user = self._users[username]
            # Remove from indexes
            if user.get("email"):
                self._email_index.pop(user["email"], None)
            if user.get("user_id"):
                self._id_index.pop(user["user_id"], None)
            # Remove user
            del self._users[username]
            return True
        return False

    async def list(self, limit: int = 100) -> list[dict]:
        return list(self._users.values())[:limit]

    async def count(self) -> int:
        """Get user count in O(1)."""
        return len(self._users)


class InMemoryTokenStore:
    """In-memory token storage (for development/testing)."""

    def __init__(self):
        self._tokens: dict[str, dict] = {}

    async def save(self, token: dict) -> None:
        token_id = token.get("id") or token.get("jti") or secrets.token_hex(16)
        token["id"] = token_id
        self._tokens[token_id] = token

    async def get(self, token_id: str) -> dict | None:
        return self._tokens.get(token_id)

    async def delete(self, token_id: str) -> None:
        self._tokens.pop(token_id, None)

    async def revoke(self, token_id: str, reason: str) -> None:
        if token_id in self._tokens:
            self._tokens[token_id]["revoked"] = True
            self._tokens[token_id]["revoked_at"] = datetime.now(UTC).isoformat()
            self._tokens[token_id]["revoked_reason"] = reason


class InMemoryKeyStore:
    """In-memory key storage (for development/testing) with user index."""

    def __init__(self):
        self._keys: dict[str, dict] = {}
        self._user_index: dict[str, list[str]] = {}  # user_id -> [key_ids]

    async def save(self, key: dict) -> None:
        key_id = key.get("key_id") or secrets.token_hex(16)
        key["key_id"] = key_id
        self._keys[key_id] = key
        
        # Update user index
        user_id = key.get("user_id")
        if user_id:
            if user_id not in self._user_index:
                self._user_index[user_id] = []
            if key_id not in self._user_index[user_id]:
                self._user_index[user_id].append(key_id)

    async def get(self, key_id: str) -> dict | None:
        return self._keys.get(key_id)

    async def list_for_user(self, user_id: str) -> list[dict]:
        # O(1) lookup via index instead of O(n) iteration
        key_ids = self._user_index.get(user_id, [])
        keys = []
        for kid in key_ids:
            if kid in self._keys:
                keys.append(self._keys[kid])
        # Sort by creation date, newest first
        keys.sort(key=lambda k: k.get("created_at", ""), reverse=True)
        return keys

    async def delete(self, key_id: str) -> bool:
        """Delete a key and update indexes."""
        if key_id in self._keys:
            key = self._keys[key_id]
            user_id = key.get("user_id")
            if user_id and user_id in self._user_index:
                if key_id in self._user_index[user_id]:
                    self._user_index[user_id].remove(key_id)
                if not self._user_index[user_id]:
                    del self._user_index[user_id]
            del self._keys[key_id]
            return True
        return False

    async def count_for_user(self, user_id: str) -> int:
        """Count keys for a user in O(1)."""
        return len(self._user_index.get(user_id, []))


class AuthStores:
    """Container for all auth stores."""

    _instance: "AuthStores | None" = None

    def __init__(
        self,
        user_store: UserStore | None = None,
        token_store: TokenStore | None = None,
        key_store: KeyStore | None = None,
    ):
        self.user_store = user_store or InMemoryUserStore()
        self.token_store = token_store or InMemoryTokenStore()
        self.key_store = key_store or InMemoryKeyStore()

    @classmethod
    def get_instance(cls) -> "AuthStores":
        """Get singleton instance."""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    @classmethod
    def reset(cls) -> None:
        """Reset singleton (for testing)."""
        cls._instance = None


def get_auth_stores() -> AuthStores:
    """FastAPI dependency for auth stores."""
    return AuthStores.get_instance()


def hash_password(password: str) -> str:
    """Hash a password using Argon2id."""
    return _password_hasher.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a password against a hash."""
    try:
        _password_hasher.verify(hashed_password, plain_password)
        return True
    except VerifyMismatchError:
        return False
    except Exception:
        return False
