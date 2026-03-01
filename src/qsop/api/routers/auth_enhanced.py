"""
Enhanced Authentication Router
Production-ready authentication with proper security
"""

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import jwt
from fastapi import APIRouter, Depends, Header, HTTPException, status
from fastapi.security import HTTPBearer, OAuth2PasswordBearer
from passlib.context import CryptContext
from pydantic import BaseModel, EmailStr, Field, validator

from qsop.settings import get_settings

router = APIRouter(prefix="/auth", tags=["Authentication"])
settings = get_settings()

# Password hashing
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# OAuth2 scheme for token authentication
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")
security = HTTPBearer()

# ============================================================================
# Request/Response Models
# ============================================================================


class LoginRequest(BaseModel):
    """Login request body with validation."""

    username: str = Field(..., min_length=3, max_length=50, description="Username or email")
    password: str = Field(..., min_length=8, max_length=100, description="User password")

    @validator("password")
    def validate_password_strength(cls, v):
        """Ensure password meets security requirements."""
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters")
        if not any(c.isupper() for c in v):
            raise ValueError("Password must contain at least one uppercase letter")
        if not any(c.islower() for c in v):
            raise ValueError("Password must contain at least one lowercase letter")
        if not any(c.isdigit() for c in v):
            raise ValueError("Password must contain at least one digit")
        return v


class RegisterRequest(BaseModel):
    """Registration request with validation."""

    username: str = Field(
        ...,
        min_length=3,
        max_length=30,
        pattern=r"^[a-z0-9_]+$",
        description="Username (alphanumeric and underscores only)",
    )
    email: EmailStr = Field(..., description="User email address")
    password: str = Field(..., min_length=8, max_length=100, description="User password")
    name: str = Field(..., min_length=2, max_length=100, description="Full display name")

    @validator("username")
    def validate_username(cls, v):
        """Validate username format."""
        if not v.islower():
            raise ValueError("Username must be lowercase")
        if v.startswith("_") or v.endswith("_"):
            raise ValueError("Username cannot start or end with underscore")
        if "__" in v:
            raise ValueError("Username cannot contain consecutive underscores")
        return v


class LoginResponse(BaseModel):
    """Login response with token."""

    access_token: str = Field(..., description="JWT access token")
    token_type: str = Field(default="bearer", description="Token type")
    expires_in: int = Field(..., description="Token expiration time in seconds")
    user_info: dict = Field(..., description="User information")


class RegisterResponse(BaseModel):
    """Registration response."""

    user_id: str = Field(..., description="Unique user identifier")
    username: str = Field(..., description="Username")
    email: str = Field(..., description="Email address")
    name: str = Field(..., description="Full name")
    created_at: datetime = Field(..., description="Account creation timestamp")


class RefreshTokenRequest(BaseModel):
    """Token refresh request."""

    refresh_token: str = Field(..., description="Refresh token")


class ErrorResponse(BaseModel):
    """Standard error response."""

    error: str = Field(..., description="Error type")
    message: str = Field(..., description="Error message")
    request_id: str = Field(..., description="Request identifier")


# ============================================================================
# In-Memory User Store (Replace with database in production)
# TODO: Replace with actual database integration
USERS_STORE = {
    # Format: { user_id: { id, username, email, name, password_hash, created_at, is_active } }
}


def get_user_by_email(email: str) -> dict | None:
    """Get user by email from store."""
    for user in USERS_STORE.values():
        if user["email"].lower() == email.lower():
            return user
    return None


def get_user_by_username(username: str) -> dict | None:
    """Get user by username from store."""
    return USERS_STORE.get(username.lower())


def create_user(username: str, email: str, password: str, name: str) -> dict:
    """Create a new user."""
    user_id = str(uuid4())
    password_hash = pwd_context.hash(password)

    user = {
        "id": user_id,
        "username": username.lower(),
        "email": email.lower(),
        "name": name,
        "password_hash": password_hash,
        "created_at": datetime.now(UTC),
        "is_active": True,
        "last_login": None,
    }

    USERS_STORE[username.lower()] = user
    return user


# ============================================================================
# JWT Token Management
# ============================================================================


def create_access_token(user: dict, expires_delta: timedelta | None = None) -> tuple[str, int]:
    """
    Create JWT access token.

    Returns:
        Tuple of (token, expires_in_seconds)
    """
    expire_minutes = getattr(settings, "access_token_expire_minutes", 60)
    if expires_delta:
        expire = datetime.now(UTC) + expires_delta
    else:
        expire = datetime.now(UTC) + timedelta(minutes=expire_minutes)

    payload = {
        "sub": user["username"],
        "user_id": user["id"],
        "email": user["email"],
        "tenant_id": "default",
        "scopes": ["read", "write", "admin"],
        "exp": int(expire.timestamp()),
        "iat": int(datetime.now(UTC).timestamp()),
        "jti": str(uuid4()),  # JWT ID for revocation support
    }

    token = jwt.encode(payload, settings.secret_key.get_secret_value(), algorithm="HS256")

    expires_in = int((expire - datetime.now(UTC)).total_seconds())

    return token, expires_in


def decode_token(token: str) -> dict:
    """Decode and validate JWT token."""
    try:
        payload = jwt.decode(token, settings.secret_key.get_secret_value(), algorithms=["HS256"])
        return payload
    except jwt.ExpiredSignatureError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has expired",
            headers={"WWW-Authenticate": "Bearer"},
        ) from e
    except jwt.InvalidTokenError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token",
            headers={"WWW-Authenticate": "Bearer"},
        ) from e


# ============================================================================
# Authentication Dependencies
# ============================================================================


async def get_current_user(
    token: str | None = Depends(oauth2_scheme),
    request_id: str | None = Header(None, alias="X-Request-ID"),
) -> dict:
    """
    Get current authenticated user from JWT token.

    Args:
        token: Bearer token from Authorization header
        request_id: Request identifier for logging

    Returns:
        User information dictionary

    Raises:
        HTTPException: If token is invalid or user not found
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    if token is None:
        raise credentials_exception

    try:
        payload = decode_token(token)
        username: str | None = payload.get("sub")
        if username is None:
            raise credentials_exception
    except HTTPException:
        raise
    except Exception as e:
        raise credentials_exception from e

    user = get_user_by_username(username)
    if user is None:
        raise credentials_exception

    if not user.get("is_active", True):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="User account is inactive"
        )

    # Add request_id to user context
    user["request_id"] = request_id

    return user


# ============================================================================
# API Endpoints
# ============================================================================


@router.post(
    "/register",
    response_model=RegisterResponse,
    status_code=status.HTTP_201_CREATED,
    responses={
        400: {"model": ErrorResponse, "description": "Invalid input or user exists"},
        409: {"model": ErrorResponse, "description": "User already exists"},
    },
)
async def register(
    request: RegisterRequest, request_id: str = Header(None, alias="X-Request-ID")
) -> dict:
    """
    Register a new user account.

    Creates a user account with the provided credentials.
    The password will be hashed using bcrypt before storage.

    **Returns:**
        - user_id: Unique identifier for the new user
        - username, email, name: User information
        - created_at: Account creation timestamp

    **Errors:**
        - 400: Invalid input data
        - 409: Username or email already exists
    """
    # Check if user already exists
    if get_user_by_username(request.username):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Username already taken",
        )

    if get_user_by_email(request.email):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email already registered",
        )

    # Create new user
    user = create_user(
        username=request.username, email=request.email, password=request.password, name=request.name
    )

    return {
        "user_id": user["id"],
        "username": user["username"],
        "email": user["email"],
        "name": user["name"],
        "created_at": user["created_at"],
    }


@router.post(
    "/login",
    response_model=LoginResponse,
    responses={
        401: {"model": ErrorResponse, "description": "Invalid credentials"},
        403: {"model": ErrorResponse, "description": "Account inactive"},
    },
)
async def login(
    request: LoginRequest, request_id: str = Header(None, alias="X-Request-ID")
) -> dict:
    """
    Authenticate user and return access token.

    Validates username/email and password, then issues a JWT access token.

    **Returns:**
        - access_token: JWT bearer token
        - token_type: Always "bearer"
        - expires_in: Token validity period in seconds
        - user_info: Basic user information

    **Errors:**
        - 401: Invalid username or password
        - 403: Account is deactivated
    """
    # Try to find user by username or email
    user = get_user_by_username(request.username)
    if not user:
        user = get_user_by_email(request.username)

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Verify password
    if not pwd_context.verify(request.password, user["password_hash"]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Check if user is active
    if not user.get("is_active", True):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account has been deactivated",
        )

    # Update last login
    user["last_login"] = datetime.now(UTC)

    # Create access token
    access_token, expires_in = create_access_token(user)

    # Prepare user info for response
    user_info = {
        "user_id": user["id"],
        "username": user["username"],
        "email": user["email"],
        "name": user["name"],
    }

    return {
        "access_token": access_token,
        "token_type": "bearer",
        "expires_in": expires_in,
        "user_info": user_info,
    }


@router.post(
    "/logout",
    responses={
        200: {"description": "Successfully logged out"},
        401: {"model": ErrorResponse, "description": "Not authenticated"},
    },
)
async def logout(current_user: dict = Depends(get_current_user)) -> dict:
    """
    Log out the current user.

    In a stateful implementation, this would invalidate the token.
    With JWT stateless tokens, tokens remain valid until expiration.
    Client should discard the token after calling this endpoint.

    TODO: Implement token revocation list for immediate logout
    """
    # TODO: Add token to revocation list
    # TODO: Remove session from cache if using session-based auth

    return {"message": "Successfully logged out", "request_id": current_user.get("request_id")}


@router.get(
    "/me",
    responses={
        200: {"description": "User information"},
        401: {"model": ErrorResponse, "description": "Not authenticated"},
    },
)
async def get_current_user_info(current_user: dict = Depends(get_current_user)) -> dict:
    """
    Get information about the currently authenticated user.

    Returns the user profile associated with the current JWT token.
    """
    return {
        "user_id": current_user["id"],
        "username": current_user["username"],
        "email": current_user["email"],
        "name": current_user.get("name"),
        "created_at": current_user.get("created_at"),
        "last_login": current_user.get("last_login"),
        "is_active": current_user.get("is_active", True),
    }


@router.post(
    "/verify-token",
    responses={
        200: {"description": "Token is valid"},
        401: {"model": ErrorResponse, "description": "Invalid or expired token"},
    },
)
async def verify_token(current_user: dict = Depends(get_current_user)) -> dict:
    """
    Verify if a token is still valid.

    Useful for checking token validity without fetching user details.
    """
    exp_timestamp = current_user.get("exp")
    if exp_timestamp is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token format")

    return {
        "valid": True,
        "user_id": current_user.get("username"),
        "expires_at": datetime.fromtimestamp(float(exp_timestamp), tz=UTC),
    }
