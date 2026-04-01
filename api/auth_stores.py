"""
Authentication stores with dependency injection support.

Provides both in-memory and database-backed storage for users, tokens, and keys.
"""

import logging
import os
import secrets
from datetime import datetime, timezone
from typing import Any, Protocol

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
    """In-memory user storage (for development/testing)."""

    def __init__(self):
        self._users: dict[str, dict] = {}
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
            admin_password = "changeme"
            logger.warning(
                "Using default admin password 'changeme' for development. "
                "Set ADMIN_PASSWORD environment variable for production."
            )

        if admin_username not in self._users:
            self._users[admin_username] = {
                "user_id": "usr_001",
                "id": "usr_001",
                "username": admin_username,
                "password_hash": _password_hasher.hash(admin_password),
                "email": os.environ.get("ADMIN_EMAIL", "admin@example.com"),
                "roles": ["admin", "user"],
                "created_at": datetime.now(timezone.utc).isoformat(),
                "kem_public_key": None,
            }
            logger.info(f"Initialized admin user: {admin_username}")

    async def get_by_username(self, username: str) -> dict | None:
        return self._users.get(username)

    async def get_by_id(self, user_id: str) -> dict | None:
        for user in self._users.values():
            if user.get("user_id") == user_id:
                return user
        return None

    async def save(self, user: dict) -> dict:
        username = user.get("username")
        if username:
            self._users[username] = user
        return user

    async def list(self, limit: int = 100) -> list[dict]:
        return list(self._users.values())[:limit]


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
            self._tokens[token_id]["revoked_at"] = datetime.now(timezone.utc).isoformat()
            self._tokens[token_id]["revoked_reason"] = reason


class InMemoryKeyStore:
    """In-memory key storage (for development/testing)."""

    def __init__(self):
        self._keys: dict[str, dict] = {}

    async def save(self, key: dict) -> None:
        key_id = key.get("key_id") or secrets.token_hex(16)
        key["key_id"] = key_id
        self._keys[key_id] = key

    async def get(self, key_id: str) -> dict | None:
        return self._keys.get(key_id)

    async def list_for_user(self, user_id: str) -> list[dict]:
        return [k for k in self._keys.values() if k.get("user_id") == user_id]


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
