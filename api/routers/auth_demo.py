"""
Server-gated Demo Mode Endpoint

Provides authenticated demo mode without client-side token forgery.
The server controls demo mode via DEMO_MODE environment variable.

This is the SECURE alternative to client-side demo token forgery.
"""

import os
import secrets
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from .auth import create_pqc_token, get_server_signing_keypair

router = APIRouter()


class DemoModeRequest(BaseModel):
    """Request for demo mode access."""

    email: str = Field(
        ...,
        min_length=3,
        max_length=50,
        pattern=r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$",
    )


@router.post("/demo-mode", status_code=200)
async def enable_demo_mode(request: DemoModeRequest):
    """
    Enable demo mode with server-generated token.

    Unlike the vulnerable client-side demo token forgery, this endpoint
    ensures that all authentication tokens are properly signed by the
    server's ML-DSA-65 signing key.

    Demo mode is only available when DEMO_MODE=true is set in environment.
    """
    # Check if demo mode is enabled on server
    demo_mode = os.getenv("DEMO_MODE", "false").lower() == "true"
    if not demo_mode:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Demo mode is not enabled on this server",
        )

    # Get server signing keypair
    from fastapi import Request

    signing_keypair = get_server_signing_keypair(Request.scope["app"])

    # Generate demo user
    demo_user_id = f"demo_{secrets.token_hex(8)}"
    username = request.email.split("@")[0]

    # Create signed token (same as normal login)
    token, signature = create_pqc_token(
        user_id=demo_user_id,
        username=username,
        roles=["user", "demo"],
        signing_keypair=signing_keypair,
    )

    return {
        "access_token": token,
        "token_type": "bearer",
        "expires_in": 86400,  # 24 hours
        "pqc_signature": signature,
        "demo_mode": True,
        "expires_at": (datetime.utcnow() + timedelta(hours=24)).isoformat(),
    }
