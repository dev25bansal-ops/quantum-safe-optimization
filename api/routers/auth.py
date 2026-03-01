"""
Authentication endpoints with PQC (Post-Quantum Cryptography).

Uses ML-DSA-65 for signing JWT tokens.
Includes rate limiting and token revocation for security.
"""

import logging
import os
import secrets
from datetime import datetime, timedelta

from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError
from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, Field

# Import PQC crypto
from quantum_safe_crypto import KemKeyPair, SigningKeyPair, py_verify

# Import security features
from api.security.rate_limiter import RateLimits, limiter
from api.security.signature_verification import SignedPayload, verify_request_signature
from api.security.token_revocation import token_revocation_service

# Import repository abstraction
try:
    from api.db.repository import get_key_store, get_token_store, get_user_store

    _db_available = True
except ImportError:
    _db_available = False
    get_user_store = None
    get_key_store = None
    get_token_store = None

logger = logging.getLogger(__name__)

router = APIRouter()
security = HTTPBearer()

# Password hasher (Argon2id - recommended for password hashing)
_password_hasher = PasswordHasher()

# Server signing keypair (initialized in app lifespan)
_server_signing_keypair: SigningKeyPair | None = None

# Lazy-initialized stores
_user_store = None
_key_store = None
_token_store = None


async def get_or_create_user_store():
    """Get or create the user store."""
    global _user_store
    if _user_store is None and get_user_store is not None:
        _user_store = await get_user_store()
    return _user_store


async def get_or_create_key_store():
    """Get or create the key store."""
    global _key_store
    if _key_store is None and get_key_store is not None:
        _key_store = await get_key_store()
    return _key_store


async def get_or_create_token_store():
    """Get or create the token store."""
    global _token_store
    if _token_store is None and get_token_store is not None:
        _token_store = await get_token_store()
    return _token_store


def get_server_signing_keypair(request: Request) -> SigningKeyPair:
    """Get the server signing keypair from app state."""
    global _server_signing_keypair
    if hasattr(request.app.state, "signing_keypair"):
        return request.app.state.signing_keypair
    if _server_signing_keypair is None:
        _server_signing_keypair = SigningKeyPair()
    return _server_signing_keypair


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


# Models
class UserCredentials(BaseModel):
    """User login credentials."""

    username: str = Field(..., min_length=3, max_length=50)
    password: str = Field(..., min_length=8)


class TokenResponse(BaseModel):
    """JWT token response."""

    access_token: str
    token_type: str = "bearer"  # noqa: S105 - Standard JWT token type
    expires_in: int
    refresh_token: str | None = None
    pqc_signature: str  # ML-DSA signature of the token


class UserInfo(BaseModel):
    """User information."""

    user_id: str
    username: str
    email: str | None = None
    roles: list[str] = []
    created_at: datetime


class KeyPairResponse(BaseModel):
    """PQC key pair for client-side encryption."""

    public_key: str  # ML-KEM public key (base64)
    key_id: str
    algorithm: str = "ML-KEM-768"
    expires_at: datetime


class PublicKeyRequest(BaseModel):
    """Request to register client's public key."""

    public_key: str  # Client's ML-KEM public key
    key_type: str = "ML-KEM-768"


class UserRegistration(BaseModel):
    """User registration request."""

    username: str = Field(..., min_length=3, max_length=50, pattern=r"^[a-zA-Z0-9_]+$")
    password: str = Field(..., min_length=8, max_length=128)
    email: str | None = Field(None, pattern=r"^[\w\.-]+@[\w\.-]+\.\w+$")
    kem_public_key: str | None = Field(
        None, description="ML-KEM-768 public key for result encryption"
    )


class RegistrationResponse(BaseModel):
    """User registration response."""

    user_id: str
    username: str
    message: str
    created_at: datetime


# In-memory storage (fallback when repository is not available)
# Password for admin is "admin123!" - hashed with Argon2id
_users_db = {
    "admin": {
        "user_id": "usr_001",
        "id": "usr_001",
        "username": "admin",
        "password_hash": "$argon2id$v=19$m=65536,t=3,p=4$RicoB40mT5DxZGqpPral7w$JLxZvZ/PbHdGVitr3eu9RW9danm83u2OADLV5rwNoAw",
        "email": "admin@example.com",
        "roles": ["admin", "user"],
        "created_at": datetime.utcnow().isoformat(),
        "kem_public_key": None,  # ML-KEM public key for result encryption
    }
}

_tokens_db = {}
_keys_db = {}


# Helper functions for database operations
async def get_user_by_username(username: str) -> dict | None:
    """Get user by username from store or in-memory."""
    store = await get_or_create_user_store()
    if store:
        try:
            return await store.get_by_username(username)
        except Exception as e:
            logger.warning(f"Failed to get user from store: {e}")
    # Fallback to in-memory
    return _users_db.get(username)


async def get_user_by_id(user_id: str) -> dict | None:
    """Get user by ID from store or in-memory."""
    store = await get_or_create_user_store()
    if store:
        try:
            return await store.get(user_id, user_id)
        except Exception as e:
            logger.warning(f"Failed to get user from store: {e}")
    # Fallback to in-memory
    for user in _users_db.values():
        if user.get("user_id") == user_id:
            return user
    return None


async def save_user(user_data: dict) -> dict:
    """Save or update user to store and in-memory cache."""
    # Always save to in-memory for sync operations
    username = user_data.get("username")
    if username:
        _users_db[username] = user_data

    # Also save to persistent store if available
    store = await get_or_create_user_store()
    if store:
        try:
            await store.upsert(user_data)
        except Exception as e:
            logger.warning(f"Failed to save user to store: {e}")

    return user_data


async def check_email_exists(email: str) -> bool:
    """Check if email already exists in the user store."""
    if not email:
        return False
    store = await get_or_create_user_store()
    if store:
        try:
            users = await store.list(limit=1000)
            for user in users:
                if user.get("email") == email:
                    return True
        except Exception as e:
            logger.warning(f"Failed to check email in store: {e}")
    # Also check in-memory
    for user in _users_db.values():
        if user.get("email") == email:
            return True
    return False


async def save_token(token: str, token_data: dict) -> dict:
    """Save token to store and in-memory cache."""
    token_data["id"] = token
    token_data["token"] = token

    # Always save to in-memory for sync verification
    _tokens_db[token] = token_data

    # Also save to persistent store if available
    store = await get_or_create_token_store()
    if store:
        try:
            await store.create(token_data)
        except Exception as e:
            logger.warning(f"Failed to save token to store: {e}")

    return token_data


async def get_token_data(token: str) -> dict | None:
    """Get token data from store."""
    store = await get_or_create_token_store()
    if store:
        try:
            return await store.get(token, None)
        except Exception as e:
            logger.warning(f"Failed to get token from store: {e}")
    # Fallback to in-memory
    return _tokens_db.get(token)


async def save_user_keys(user_id: str, key_data: dict) -> dict:
    """Save user's encryption keys to store."""
    store = await get_or_create_key_store()
    if store:
        try:
            key_data["user_id"] = user_id
            return await store.upsert(key_data)
        except Exception as e:
            logger.warning(f"Failed to save keys to store: {e}")
    # Also save to in-memory
    _keys_db[user_id] = key_data
    return key_data


async def get_user_keys(user_id: str) -> dict | None:
    """Get user's encryption keys from store."""
    store = await get_or_create_key_store()
    if store:
        try:
            return await store.get_by_user(user_id)
        except Exception as e:
            logger.warning(f"Failed to get keys from store: {e}")
    # Fallback to in-memory
    return _keys_db.get(user_id)


def create_pqc_token(
    user_id: str, username: str, roles: list[str], signing_keypair: SigningKeyPair
) -> tuple[str, str]:
    """
    Create a PQC-signed JWT token using ML-DSA-65.

    Returns (token, signature).
    """
    import base64
    import json

    header = {"alg": "ML-DSA-65", "typ": "JWT"}
    payload = {
        "sub": user_id,
        "username": username,
        "roles": roles,
        "iat": datetime.utcnow().timestamp(),
        "exp": (datetime.utcnow() + timedelta(hours=24)).timestamp(),
        "jti": secrets.token_hex(16),
    }

    header_b64 = base64.urlsafe_b64encode(json.dumps(header).encode()).decode().rstrip("=")
    payload_b64 = base64.urlsafe_b64encode(json.dumps(payload).encode()).decode().rstrip("=")

    token_data = f"{header_b64}.{payload_b64}"

    # Sign with ML-DSA-65
    signature = signing_keypair.sign(token_data.encode())

    # Use first 86 chars of signature for token (URL-safe truncation)
    sig_truncated = signature[:86].replace("+", "-").replace("/", "_")
    token = f"{token_data}.{sig_truncated}"

    return token, signature


def verify_pqc_token(token: str, signing_keypair: SigningKeyPair | None = None) -> dict | None:
    """
    Verify a PQC-signed JWT token.

    Note: Full signature verification requires the server's signing keypair.
    For now, we verify expiration and structure, and optionally the signature.

    Returns payload if valid, None otherwise.
    """
    import base64
    import json

    try:
        parts = token.split(".")
        if len(parts) != 3:
            return None

        header_b64, payload_b64, sig_truncated = parts

        # Pad base64 if needed
        payload_b64_padded = (
            payload_b64 + "=" * (4 - len(payload_b64) % 4) if len(payload_b64) % 4 else payload_b64
        )

        payload = json.loads(base64.urlsafe_b64decode(payload_b64_padded))

        # Check expiration
        if payload.get("exp", 0) < datetime.utcnow().timestamp():
            return None

        # Enforce active token check unless explicitly bypassed
        allow_token_db_bypass = os.getenv("ALLOW_TOKEN_DB_BYPASS", "false").lower() == "true"
        token_record = _tokens_db.get(token)
        if token_record is None and not allow_token_db_bypass:
            return None

        # Verify signature if we have server signing keypair and stored full signature
        if signing_keypair and token_record and token_record.get("full_signature"):
            token_data = f"{header_b64}.{payload_b64}"
            signature = token_record["full_signature"]
            if not py_verify(token_data.encode("utf-8"), signature, signing_keypair.public_key):
                return None

        return payload
    except Exception:
        return None


async def check_token_revocation(token_jti: str) -> bool:
    """Check if a token has been revoked."""
    return await token_revocation_service.is_revoked(token_jti)


async def get_current_user(
    request: Request, credentials: HTTPAuthorizationCredentials = Depends(security)
) -> dict:
    """Dependency to get current authenticated user."""
    token = credentials.credentials

    # Get signing keypair for verification (if available)
    signing_keypair = None
    if hasattr(request.app.state, "signing_keypair"):
        signing_keypair = request.app.state.signing_keypair

    payload = verify_pqc_token(token, signing_keypair)

    if payload is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Check if token has been revoked
    token_jti = payload.get("jti")
    if token_jti and await check_token_revocation(token_jti):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has been revoked",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return payload


# Endpoints
@router.post("/login", response_model=TokenResponse)
@limiter.limit(RateLimits.LOGIN)
async def login(request: Request, credentials: UserCredentials):
    """
    Authenticate user and return PQC-signed JWT token.

    The token is signed using ML-DSA-65 for post-quantum security.
    Rate limited to prevent brute-force attacks.
    """
    # Validate credentials - try store first, then in-memory
    user = await get_user_by_username(credentials.username)

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
        )

    # Verify password hash
    if not verify_password(credentials.password, user["password_hash"]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
        )

    # Get server signing keypair
    signing_keypair = get_server_signing_keypair(request)

    # Create PQC-signed token with ML-DSA-65
    token, signature = create_pqc_token(
        user["user_id"],
        user["username"],
        user["roles"],
        signing_keypair,
    )

    # Store token for revocation checking
    token_data = {
        "user_id": user["user_id"],
        "created_at": datetime.utcnow().isoformat(),
        "full_signature": signature,  # Store full signature for verification
    }
    await save_token(token, token_data)

    return TokenResponse(
        access_token=token,
        expires_in=86400,  # 24 hours
        pqc_signature=signature,
    )


@router.post("/register", response_model=RegistrationResponse, status_code=201)
@limiter.limit(RateLimits.REGISTER)
async def register(request: Request, registration: UserRegistration):
    """
    Register a new user account.

    Optionally accepts an ML-KEM-768 public key for encrypting job results.
    Rate limited to prevent abuse.
    """
    # Check if username already exists
    existing_user = await get_user_by_username(registration.username)
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Username already exists",
        )

    # Check email uniqueness if provided
    if registration.email:
        if await check_email_exists(registration.email):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Email already registered",
            )

    # Generate user ID
    user_id = f"usr_{secrets.token_hex(6)}"

    # Hash password with Argon2id
    password_hash = hash_password(registration.password)

    # Create user record
    created_at = datetime.utcnow()
    user_data = {
        "user_id": user_id,
        "id": user_id,  # For Cosmos DB
        "username": registration.username,
        "password_hash": password_hash,
        "email": registration.email,
        "roles": ["user"],  # Default role
        "created_at": created_at.isoformat(),
        "kem_public_key": registration.kem_public_key,
    }

    # Save to store and in-memory
    await save_user(user_data)

    return RegistrationResponse(
        user_id=user_id,
        username=registration.username,
        message="Registration successful. You can now login.",
        created_at=created_at,
    )


@router.post("/refresh", response_model=TokenResponse)
@limiter.limit(RateLimits.REFRESH_TOKEN)
async def refresh_token(request: Request, current_user: dict = Depends(get_current_user)):
    """Refresh an existing token."""
    signing_keypair = get_server_signing_keypair(request)

    # Revoke the old token
    old_jti = current_user.get("jti")
    if old_jti:
        await token_revocation_service.revoke_token(
            old_jti,
            reason="refresh",
            user_id=current_user.get("sub"),
        )

    token, signature = create_pqc_token(
        current_user["sub"],
        current_user["username"],
        current_user["roles"],
        signing_keypair,
    )

    # Store refreshed token for verification
    token_data = {
        "user_id": current_user["sub"],
        "created_at": datetime.utcnow().isoformat(),
        "full_signature": signature,
    }
    await save_token(token, token_data)

    return TokenResponse(
        access_token=token,
        expires_in=86400,
        pqc_signature=signature,
    )


@router.post("/logout")
@limiter.limit(RateLimits.LOGOUT)
async def logout(request: Request, current_user: dict = Depends(get_current_user)):
    """
    Invalidate current token by adding to revocation list.

    The token JTI is stored in Redis (or memory fallback) and will be
    rejected on future authentication attempts.
    """
    token_jti = current_user.get("jti")
    if token_jti:
        await token_revocation_service.revoke_token(
            token_jti,
            reason="logout",
            user_id=current_user.get("sub"),
        )

    return {"message": "Successfully logged out", "revoked_jti": token_jti}


@router.get("/me", response_model=UserInfo)
async def get_current_user_info(current_user: dict = Depends(get_current_user)):
    """Get current user information."""
    user = await get_user_by_username(current_user["username"])

    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    return UserInfo(
        user_id=user["user_id"],
        username=user["username"],
        email=user.get("email"),
        roles=user["roles"],
        created_at=user["created_at"],
    )


@router.post("/keys/generate", response_model=KeyPairResponse)
@limiter.limit(RateLimits.KEY_GENERATION)
async def generate_encryption_key(request: Request, current_user: dict = Depends(get_current_user)):
    """
    Generate a new ML-KEM-768 key pair for the user.

    The public key can be used by the server to encrypt sensitive data
    that only the user can decrypt. The secret key is returned securely
    and should be stored by the client.
    """
    # Generate actual ML-KEM-768 key pair
    keypair = KemKeyPair()

    key_id = f"key_{secrets.token_hex(8)}"
    expires_at = datetime.utcnow() + timedelta(days=30)

    # Store public key on server (secret key stays with client)
    key_data = {
        "id": key_id,
        "user_id": current_user["sub"],
        "public_key": keypair.public_key,
        "created_at": datetime.utcnow(),
        "expires_at": expires_at,
        "algorithm": "ML-KEM-768",
    }
    await save_user_keys(current_user["sub"], key_data)

    return KeyPairResponse(
        public_key=keypair.public_key,
        key_id=key_id,
        expires_at=expires_at,
    )


@router.post("/keys/register")
async def register_public_key(
    request: PublicKeyRequest,
    current_user: dict = Depends(get_current_user),
):
    """
    Register a client-generated public key.

    Allows clients to generate their own ML-KEM keys and register
    the public key with the server.
    """
    key_id = f"key_{secrets.token_hex(8)}"

    key_data = {
        "id": key_id,
        "user_id": current_user["sub"],
        "public_key": request.public_key,
        "key_type": request.key_type,
        "created_at": datetime.utcnow(),
        "client_generated": True,
    }
    await save_user_keys(current_user["sub"], key_data)

    # Also update user's primary KEM public key for result encryption
    username = current_user.get("username")
    user = await get_user_by_username(username) if username else None
    if user:
        user["kem_public_key"] = request.public_key
        await save_user(user)

    return {
        "key_id": key_id,
        "message": "Public key registered successfully",
    }


@router.put("/keys/encryption-key")
async def update_encryption_key(
    request: PublicKeyRequest,
    current_user: dict = Depends(get_current_user),
):
    """
    Update the user's primary ML-KEM public key for result encryption.

    This key is used to encrypt job results so only the user can decrypt them.
    """
    username = current_user.get("username")
    user = await get_user_by_username(username)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Update user with new encryption key
    user["kem_public_key"] = request.public_key
    await save_user(user)

    return {
        "message": "Encryption key updated successfully",
        "key_type": request.key_type,
    }


@router.get("/keys/{key_id}")
async def get_key_info(
    key_id: str,
    current_user: dict = Depends(get_current_user),
):
    """Get information about a registered key."""
    key_info = await get_user_keys(current_user["sub"])

    if not key_info or key_info.get("id") != key_id:
        raise HTTPException(status_code=404, detail="Key not found")

    if key_info["user_id"] != current_user["sub"]:
        raise HTTPException(status_code=403, detail="Access denied")

    return {
        "key_id": key_id,
        "created_at": key_info["created_at"].isoformat()
        if isinstance(key_info.get("created_at"), datetime)
        else key_info.get("created_at", "unknown"),
        "expires_at": key_info.get("expires_at", "never").isoformat()
        if isinstance(key_info.get("expires_at"), datetime)
        else "never",
        "algorithm": key_info.get("key_type", "ML-KEM-768"),
    }


@router.post("/verify-signature")
async def verify_signed_payload(
    signed_payload: SignedPayload,
    current_user: dict = Depends(get_current_user),
):
    """
    Verify an ML-DSA signature on an encrypted payload.

    This endpoint validates that a signed payload:
    1. Has a valid ML-DSA-65 signature
    2. Was signed within the acceptable time window
    3. (Optionally) matches the expected signer

    Use this before decrypting sensitive payloads to ensure authenticity.
    """
    # Verify the signature
    result = verify_request_signature(signed_payload)

    if not result.valid:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Signature verification failed: {result.error}",
        )

    return {
        "valid": True,
        "signer_public_key": result.signer_key[:40] + "..." if result.signer_key else None,
        "payload_size": len(result.payload_data) if result.payload_data else 0,
        "message": "Signature verified successfully",
    }


@router.post("/revoke-all-tokens")
@limiter.limit("1/minute")  # Very strict limit
async def revoke_all_user_tokens(
    request: Request,
    current_user: dict = Depends(get_current_user),
):
    """
    Revoke all tokens for the current user.

    Use this after a security event like password change.
    Rate limited to 1 request per minute.
    """
    user_id = current_user.get("sub")
    count = await token_revocation_service.revoke_all_user_tokens(user_id, reason="user_initiated")

    return {
        "message": "All tokens revoked",
        "revoked_count": count,
        "user_id": user_id,
    }
