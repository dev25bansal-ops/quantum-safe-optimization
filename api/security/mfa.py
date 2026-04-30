"""
Multi-Factor Authentication (MFA) Support.

Provides TOTP (Time-based One-Time Password) authentication.
"""

import base64
import hashlib
import hmac
import io
import logging
import os
import secrets
import struct
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

logger = logging.getLogger(__name__)

# TOTP configuration
TOTP_DIGITS = 6
TOTP_INTERVAL = 30  # seconds
TOTP_WINDOW = 1  # Allow 1 interval before/after for clock skew


@dataclass
class MFASetup:
    """MFA setup information."""

    secret: str
    provisioning_uri: str
    qr_code_url: str
    backup_codes: list[str]


@dataclass
class MFAStatus:
    """MFA status for a user."""

    enabled: bool
    method: str | None
    verified_at: str | None
    last_used_at: str | None


def generate_secret() -> str:
    """Generate a new TOTP secret."""
    return base64.b32encode(secrets.token_bytes(20)).decode().rstrip("=")


def _get_time_counter(timestamp: int | None = None) -> int:
    """Get the TOTP time counter for a timestamp."""
    if timestamp is None:
        timestamp = int(time.time())
    return timestamp // TOTP_INTERVAL


def _hotp(secret: str, counter: int) -> int:
    """Generate HOTP (HMAC-based One-Time Password)."""
    # Decode the secret
    key = base64.b32decode(secret + "=" * (8 - len(secret) % 8))

    # Create counter as bytes
    counter_bytes = struct.pack(">Q", counter)

    # Calculate HMAC
    hmac_hash = hmac.new(key, counter_bytes, hashlib.sha1).digest()

    # Dynamic truncation
    offset = hmac_hash[-1] & 0x0F
    code = struct.unpack(">I", hmac_hash[offset : offset + 4])[0]
    code = code & 0x7FFFFFFF

    return code % (10**TOTP_DIGITS)


def generate_totp(secret: str, timestamp: int | None = None) -> str:
    """Generate TOTP code for current time."""
    counter = _get_time_counter(timestamp)
    code = _hotp(secret, counter)
    return f"{code:0{TOTP_DIGITS}d}"


def verify_totp(secret: str, code: str, window: int = TOTP_WINDOW) -> bool:
    """
    Verify a TOTP code.

    Args:
        secret: The user's TOTP secret
        code: The code to verify
        window: Number of intervals to check before/after current time

    Returns:
        True if the code is valid
    """
    if not code or len(code) != TOTP_DIGITS:
        return False

    current_counter = _get_time_counter()

    # Check current and surrounding intervals
    for offset in range(-window, window + 1):
        counter = current_counter + offset
        expected_code = _hotp(secret, counter)
        if hmac.compare_digest(f"{expected_code:0{TOTP_DIGITS}d}", code):
            return True

    return False


def generate_backup_codes(count: int = 10) -> list[str]:
    """Generate backup codes for MFA recovery."""
    codes = []
    for _ in range(count):
        code = secrets.token_hex(4).upper()  # 8-character hex code
        codes.append(f"{code[:4]}-{code[4:]}")
    return codes


def hash_backup_code(code: str) -> str:
    """Hash a backup code for storage."""
    return hashlib.sha256(code.encode()).hexdigest()


def get_provisioning_uri(secret: str, username: str, issuer: str = "Quantum-Safe Platform") -> str:
    """Generate provisioning URI for authenticator apps."""
    import urllib.parse

    label = urllib.parse.quote(f"{issuer}:{username}")
    params = urllib.parse.urlencode(
        {
            "secret": secret,
            "issuer": issuer,
            "algorithm": "SHA1",
            "digits": TOTP_DIGITS,
            "period": TOTP_INTERVAL,
        }
    )
    return f"otpauth://totp/{label}?{params}"


def get_qr_code_url(provisioning_uri: str) -> str:
    """Generate URL for QR code image (using Google Chart API or similar)."""
    import urllib.parse

    encoded_uri = urllib.parse.quote(provisioning_uri)
    return f"https://chart.googleapis.com/chart?chs=200x200&cht=qr&chl={encoded_uri}&choe=UTF-8"


# Storage functions (would be replaced with actual database calls)
_mfa_secrets: dict[str, dict[str, Any]] = {}


async def setup_mfa(user_id: str, username: str) -> MFASetup:
    """
    Set up MFA for a user.

    Returns setup information including secret and backup codes.
    """
    secret = generate_secret()
    backup_codes = generate_backup_codes()
    provisioning_uri = get_provisioning_uri(secret, username)
    qr_code_url = get_qr_code_url(provisioning_uri)

    # Store temporarily (not verified yet)
    _mfa_secrets[user_id] = {
        "secret": secret,
        "backup_codes": [hash_backup_code(code) for code in backup_codes],
        "verified": False,
        "created_at": datetime.now(UTC).isoformat(),
    }

    return MFASetup(
        secret=secret,
        provisioning_uri=provisioning_uri,
        qr_code_url=qr_code_url,
        backup_codes=backup_codes,
    )


async def verify_mfa_setup(user_id: str, code: str) -> bool:
    """
    Verify MFA setup with a code.

    Returns True if the code is valid, marking MFA as enabled.
    """
    user_mfa = _mfa_secrets.get(user_id)
    if not user_mfa:
        return False

    if verify_totp(user_mfa["secret"], code):
        user_mfa["verified"] = True
        user_mfa["verified_at"] = datetime.now(UTC).isoformat()
        return True

    return False


async def verify_mfa_code(user_id: str, code: str) -> bool:
    """Verify an MFA code during login."""
    user_mfa = _mfa_secrets.get(user_id)
    if not user_mfa or not user_mfa.get("verified"):
        return False

    # Check TOTP code
    if verify_totp(user_mfa["secret"], code):
        user_mfa["last_used_at"] = datetime.now(UTC).isoformat()
        return True

    # Check backup codes
    hashed_code = hash_backup_code(code)
    if hashed_code in user_mfa.get("backup_codes", []):
        # Remove used backup code
        user_mfa["backup_codes"].remove(hashed_code)
        user_mfa["last_used_at"] = datetime.now(UTC).isoformat()
        logger.info("mfa_backup_code_used", user_id=user_id)
        return True

    return False


async def get_mfa_status(user_id: str) -> MFAStatus:
    """Get MFA status for a user."""
    user_mfa = _mfa_secrets.get(user_id)

    if not user_mfa or not user_mfa.get("verified"):
        return MFAStatus(
            enabled=False,
            method=None,
            verified_at=None,
            last_used_at=None,
        )

    return MFAStatus(
        enabled=True,
        method="totp",
        verified_at=user_mfa.get("verified_at"),
        last_used_at=user_mfa.get("last_used_at"),
    )


async def disable_mfa(user_id: str) -> bool:
    """Disable MFA for a user."""
    if user_id in _mfa_secrets:
        del _mfa_secrets[user_id]
        return True
    return False


async def regenerate_backup_codes(user_id: str) -> list[str] | None:
    """Regenerate backup codes for a user."""
    user_mfa = _mfa_secrets.get(user_id)
    if not user_mfa or not user_mfa.get("verified"):
        return None

    backup_codes = generate_backup_codes()
    user_mfa["backup_codes"] = [hash_backup_code(code) for code in backup_codes]
    return backup_codes
