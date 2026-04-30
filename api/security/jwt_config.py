"""
JWT Configuration - Secure secret key management.

Ensures JWT secrets are properly configured in production.
"""

import logging
import os

logger = logging.getLogger(__name__)


def get_jwt_secret() -> str:
    """
    Get JWT secret from environment.

    In production (APP_ENV=production), the secret MUST be set.
    In development, a warning is logged but a fallback is provided.

    Raises:
        RuntimeError: If secret not set in production environment.
    """
    secret = os.getenv("JWT_SECRET") or os.getenv("SECRET_KEY")
    app_env = os.getenv("APP_ENV", "development")

    if not secret:
        if app_env == "production":
            raise RuntimeError(
                "SECURITY CRITICAL: JWT_SECRET or SECRET_KEY environment variable "
                "must be set in production. Refusing to start with insecure configuration."
            )

        secret = "dev-secret-key-change-in-production"
        logger.warning(
            "Using insecure default JWT secret for development. "
            "Set JWT_SECRET environment variable for production."
        )

    if len(secret) < 32:
        logger.warning(
            f"JWT secret is only {len(secret)} characters. "
            "Recommend using at least 32 characters for security."
        )

    return secret


def validate_jwt_config() -> bool:
    """Validate JWT configuration is secure."""
    try:
        secret = get_jwt_secret()

        if "dev-secret" in secret.lower() or "change" in secret.lower():
            if os.getenv("APP_ENV") == "production":
                return False
            logger.warning("JWT secret appears to be a development/default value")

        return True
    except RuntimeError:
        return False
