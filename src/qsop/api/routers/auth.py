"""Authentication router."""

from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import uuid4

import jwt
from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, EmailStr

from qsop.settings import get_settings

router = APIRouter()
settings = get_settings()


class LoginRequest(BaseModel):
    """Login request body."""

    username: str
    password: str


class LoginResponse(BaseModel):
    """Login response body."""

    access_token: str
    token_type: str = "bearer"


class RegisterRequest(BaseModel):
    """Registration request body."""

    username: str
    email: EmailStr
    password: str


class RegisterResponse(BaseModel):
    """Registration response body."""

    user_id: str
    username: str
    created_at: datetime


@router.post("/register", response_model=RegisterResponse)
async def register(request: RegisterRequest) -> Any:
    """Register a new user (Mock implementation)."""
    # In a real app, we would save to the database
    user_id = str(uuid4())
    return {
        "user_id": user_id,
        "username": request.username,
        "created_at": datetime.now(UTC),
    }


@router.post("/login", response_model=LoginResponse)
async def login(request: LoginRequest) -> Any:
    """Login a user and return a JWT (Mock implementation)."""
    # In a real app, we would verify credentials against the database
    # For now, we'll accept any password as long as it's not empty
    if not request.password:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
        )

    # Create JWT
    expiration = datetime.now(UTC) + timedelta(days=1)
    payload = {
        "sub": request.username,
        "tenant_id": "default",
        "scopes": ["read", "write"],
        "exp": int(expiration.timestamp()),
    }

    token = jwt.encode(
        payload,
        settings.secret_key.get_secret_value(),
        algorithm="HS256",
    )

    return {
        "access_token": token,
        "token_type": "bearer",
    }
