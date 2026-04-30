"""
Shared authentication dependencies for all routers.

Provides real auth integration replacing stub implementations
across billing, marketplace, federation, and tenant routers.
"""

import logging
from typing import Optional

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

logger = logging.getLogger(__name__)

security = HTTPBearer()


async def get_current_user_from_token(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    request: Request = None,
) -> dict:
    """
    Extract and validate user from JWT token.
    
    This replaces the stub get_user_id() functions across routers.
    
    Args:
        credentials: Bearer token from Authorization header
        request: FastAPI request object
        
    Returns:
        User dictionary with claims
        
    Raises:
        HTTPException: If token is invalid or expired
    """
    try:
        # Import actual auth functions
        from api.routers.auth import get_current_user, verify_pqc_token
        
        # Use the real auth implementation
        user = await get_current_user(credentials.credentials)
        return user
        
    except ImportError:
        # Fallback: Try alternative auth module
        try:
            from qsop.api.routers.auth import get_current_user
            user = await get_current_user(credentials.credentials)
            return user
        except (ImportError, Exception) as e:
            logger.warning("auth_integration_fallback", error=str(e))
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Authentication service unavailable",
                headers={"WWW-Authenticate": "Bearer"},
            )
    except Exception as e:
        logger.warning("token_validation_failed", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )


async def get_tenant_from_user(
    current_user: dict = Depends(get_current_user_from_token),
) -> str:
    """
    Extract tenant ID from authenticated user.
    
    Replaces stub get_tenant_id() functions.
    
    Args:
        current_user: Authenticated user dictionary
        
    Returns:
        Tenant ID string
    """
    tenant_id = current_user.get("tenant_id") or current_user.get("sub", "").split(":")[0]
    
    if not tenant_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No tenant associated with user",
        )
    
    return tenant_id


async def get_user_id(
    current_user: dict = Depends(get_current_user_from_token),
) -> str:
    """
    Extract user ID from authenticated user.
    
    Replaces stub get_user_id() functions.
    
    Args:
        current_user: Authenticated user dictionary
        
    Returns:
        User ID string
    """
    user_id = current_user.get("sub") or current_user.get("user_id")
    
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="No user ID in token",
        )
    
    return user_id


async def check_user_permission(
    required_permission: str,
    current_user: dict = Depends(get_current_user_from_token),
) -> bool:
    """
    Check if user has required permission.
    
    Replaces check_permission_stub() that always returned True.
    
    Args:
        required_permission: Permission string to check
        current_user: Authenticated user dictionary
        
    Returns:
        True if user has permission
        
    Raises:
        HTTPException: If user lacks permission
    """
    # Get user permissions from token claims
    permissions = current_user.get("permissions", [])
    roles = current_user.get("roles", [])
    
    # Admin role has all permissions
    if "admin" in roles:
        return True
    
    # Check if user has the required permission
    if required_permission in permissions:
        return True
    
    # Check role-based permissions
    role_permissions = {
        "admin": ["*"],
        "operator": ["read", "write", "execute"],
        "analyst": ["read", "analyze"],
        "user": ["read"],
    }
    
    for role in roles:
        role_perms = role_permissions.get(role, [])
        if "*" in role_perms or required_permission in role_perms:
            return True
    
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail=f"User lacks required permission: {required_permission}",
    )
