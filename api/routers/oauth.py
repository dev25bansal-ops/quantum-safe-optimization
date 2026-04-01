"""
OAuth 2.0 / OIDC Integration for Enterprise SSO.

Supports:
- Authorization Code Flow
- Client Credentials Flow
- PKCE for public clients
- OpenID Connect Discovery
- Multi-tenant SSO (Azure AD, Google, Okta, etc.)
"""

import base64
import hashlib
import logging
import os
import secrets
import urllib.parse
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any

import jwt
from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, Field, HttpUrl

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/oauth", tags=["OAuth / SSO"])


class OAuthProvider(str, Enum):
    """Supported OAuth providers."""

    AZURE_AD = "azure_ad"
    GOOGLE = "google"
    OKTA = "okta"
    GITHUB = "github"
    GITLAB = "gitlab"
    CUSTOM = "custom"


class OAuthConfig(BaseModel):
    """OAuth provider configuration."""

    provider: OAuthProvider
    client_id: str
    client_secret: str | None = None
    authorization_url: str
    token_url: str
    userinfo_url: str | None = None
    jwks_url: str | None = None
    issuer: str | None = None
    scope: str = "openid profile email"
    redirect_uri: str | None = None


class OAuthAuthorizeRequest(BaseModel):
    """OAuth authorization request."""

    provider: OAuthProvider
    state: str | None = None
    redirect_uri: str | None = None
    scope: str | None = None
    code_challenge: str | None = None
    code_challenge_method: str = "S256"


class OAuthTokenRequest(BaseModel):
    """OAuth token exchange request."""

    provider: OAuthProvider
    code: str
    state: str
    code_verifier: str | None = None
    redirect_uri: str | None = None


class OAuthTokenResponse(BaseModel):
    """OAuth token response."""

    access_token: str
    token_type: str = "Bearer"
    expires_in: int
    refresh_token: str | None = None
    id_token: str | None = None
    scope: str | None = None


class OAuthUserInfo(BaseModel):
    """OAuth user information."""

    sub: str
    email: str | None = None
    email_verified: bool = False
    name: str | None = None
    given_name: str | None = None
    family_name: str | None = None
    picture: str | None = None
    roles: list[str] = []
    provider: str
    organization_id: str | None = None


class OIDCDiscovery(BaseModel):
    """OpenID Connect Discovery document."""

    issuer: str
    authorization_endpoint: str
    token_endpoint: str
    userinfo_endpoint: str | None = None
    jwks_uri: str | None = None
    response_types_supported: list[str] = ["code"]
    subject_types_supported: list[str] = ["public"]
    id_token_signing_alg_values_supported: list[str] = ["RS256", "ES256"]
    scopes_supported: list[str] = ["openid", "profile", "email"]
    code_challenge_methods_supported: list[str] = ["S256", "plain"]


_oauth_states: dict[str, dict] = {}
_oauth_configs: dict[OAuthProvider, OAuthConfig] = {}


def get_oauth_config(provider: OAuthProvider) -> OAuthConfig | None:
    """Get OAuth configuration for a provider."""
    if provider in _oauth_configs:
        return _oauth_configs[provider]

    env_prefix = provider.value.upper()

    client_id = os.getenv(f"{env_prefix}_CLIENT_ID")
    client_secret = os.getenv(f"{env_prefix}_CLIENT_SECRET")

    if not client_id:
        return None

    defaults = {
        OAuthProvider.AZURE_AD: {
            "authorization_url": f"https://login.microsoftonline.com/{os.getenv('AZURE_TENANT_ID', 'common')}/oauth2/v2.0/authorize",
            "token_url": f"https://login.microsoftonline.com/{os.getenv('AZURE_TENANT_ID', 'common')}/oauth2/v2.0/token",
            "userinfo_url": "https://graph.microsoft.com/v1.0/me",
            "issuer": f"https://login.microsoftonline.com/{os.getenv('AZURE_TENANT_ID', 'common')}/v2.0",
        },
        OAuthProvider.GOOGLE: {
            "authorization_url": "https://accounts.google.com/o/oauth2/v2/auth",
            "token_url": "https://oauth2.googleapis.com/token",
            "userinfo_url": "https://www.googleapis.com/oauth2/v3/userinfo",
            "jwks_url": "https://www.googleapis.com/oauth2/v3/certs",
            "issuer": "https://accounts.google.com",
        },
        OAuthProvider.GITHUB: {
            "authorization_url": "https://github.com/login/oauth/authorize",
            "token_url": "https://github.com/login/oauth/access_token",
            "userinfo_url": "https://api.github.com/user",
            "issuer": "https://github.com",
        },
        OAuthProvider.OKTA: {
            "authorization_url": f"https://{os.getenv('OKTA_DOMAIN')}/oauth2/v1/authorize",
            "token_url": f"https://{os.getenv('OKTA_DOMAIN')}/oauth2/v1/token",
            "userinfo_url": f"https://{os.getenv('OKTA_DOMAIN')}/oauth2/v1/userinfo",
            "jwks_url": f"https://{os.getenv('OKTA_DOMAIN')}/oauth2/v1/keys",
            "issuer": f"https://{os.getenv('OKTA_DOMAIN')}",
        },
        OAuthProvider.GITLAB: {
            "authorization_url": f"https://{os.getenv('GITLAB_DOMAIN', 'gitlab.com')}/oauth/authorize",
            "token_url": f"https://{os.getenv('GITLAB_DOMAIN', 'gitlab.com')}/oauth/token",
            "userinfo_url": f"https://{os.getenv('GITLAB_DOMAIN', 'gitlab.com')}/api/v4/user",
            "issuer": f"https://{os.getenv('GITLAB_DOMAIN', 'gitlab.com')}",
        },
        OAuthProvider.CUSTOM: {
            "authorization_url": os.getenv("CUSTOM_AUTH_URL", ""),
            "token_url": os.getenv("CUSTOM_TOKEN_URL", ""),
            "userinfo_url": os.getenv("CUSTOM_USERINFO_URL"),
            "jwks_url": os.getenv("CUSTOM_JWKS_URL"),
            "issuer": os.getenv("CUSTOM_ISSUER"),
        },
    }

    config_data = defaults.get(provider, {})
    config_data.update(
        {
            "provider": provider,
            "client_id": client_id,
            "client_secret": client_secret,
            "scope": os.getenv(f"{env_prefix}_SCOPE", "openid profile email"),
        }
    )

    config = OAuthConfig(**config_data)
    _oauth_configs[provider] = config
    return config


def generate_pkce_challenge() -> tuple[str, str]:
    """Generate PKCE code verifier and challenge.

    Returns (code_verifier, code_challenge).
    """
    code_verifier = secrets.token_urlsafe(64)
    code_challenge = (
        base64.urlsafe_b64encode(hashlib.sha256(code_verifier.encode()).digest())
        .decode()
        .rstrip("=")
    )
    return code_verifier, code_challenge


def create_jwt_token(user_info: dict, expires_in: int = 3600) -> str:
    """Create a JWT token for the authenticated user."""
    from api.security.jwt_config import get_jwt_secret

    secret = get_jwt_secret()

    payload = {
        "sub": user_info.get("sub"),
        "email": user_info.get("email"),
        "name": user_info.get("name"),
        "roles": user_info.get("roles", ["user"]),
        "provider": user_info.get("provider"),
        "iat": datetime.now(timezone.utc),
        "exp": datetime.now(timezone.utc) + timedelta(seconds=expires_in),
        "jti": secrets.token_hex(16),
    }

    return jwt.encode(payload, secret, algorithm="HS256")


@router.get("/.well-known/openid-configuration", response_model=OIDCDiscovery)
async def openid_discovery(request: Request):
    """OpenID Connect Discovery endpoint."""
    base_url = str(request.base_url).rstrip("/")

    return OIDCDiscovery(
        issuer=f"{base_url}",
        authorization_endpoint=f"{base_url}/oauth/authorize",
        token_endpoint=f"{base_url}/oauth/token",
        userinfo_endpoint=f"{base_url}/oauth/userinfo",
        jwks_uri=f"{base_url}/oauth/.well-known/jwks.json",
    )


@router.get("/providers")
async def list_oauth_providers():
    """List available OAuth providers."""
    providers = []
    for provider in OAuthProvider:
        config = get_oauth_config(provider)
        if config and config.client_id:
            providers.append(
                {
                    "provider": provider.value,
                    "name": provider.value.replace("_", " ").title(),
                    "configured": True,
                }
            )
    return {"providers": providers}


@router.get("/authorize")
async def oauth_authorize(
    request: Request,
    provider: OAuthProvider,
    redirect_uri: str | None = None,
    state: str | None = None,
    scope: str | None = None,
):
    """Initiate OAuth authorization flow."""
    config = get_oauth_config(provider)
    if not config:
        raise HTTPException(status_code=400, detail=f"Provider {provider} not configured")

    if not state:
        state = secrets.token_urlsafe(32)

    code_verifier, code_challenge = generate_pkce_challenge()

    _oauth_states[state] = {
        "provider": provider,
        "code_verifier": code_verifier,
        "redirect_uri": redirect_uri or config.redirect_uri,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }

    params = {
        "client_id": config.client_id,
        "response_type": "code",
        "scope": scope or config.scope,
        "redirect_uri": redirect_uri or config.redirect_uri or f"{request.base_url}oauth/callback",
        "state": state,
        "code_challenge": code_challenge,
        "code_challenge_method": "S256",
    }

    if provider == OAuthProvider.AZURE_AD:
        params["response_mode"] = "query"

    auth_url = f"{config.authorization_url}?{urllib.parse.urlencode(params)}"

    return RedirectResponse(url=auth_url)


@router.get("/callback")
async def oauth_callback(
    request: Request,
    code: str,
    state: str,
    error: str | None = None,
    error_description: str | None = None,
):
    """OAuth callback endpoint."""
    if error:
        raise HTTPException(status_code=400, detail=f"{error}: {error_description}")

    state_data = _oauth_states.pop(state, None)
    if not state_data:
        raise HTTPException(status_code=400, detail="Invalid or expired state")

    provider = state_data["provider"]
    config = get_oauth_config(provider)
    if not config:
        raise HTTPException(status_code=400, detail="Provider not configured")

    import httpx

    token_data = {
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": state_data["redirect_uri"],
        "client_id": config.client_id,
        "code_verifier": state_data["code_verifier"],
    }

    if config.client_secret:
        token_data["client_secret"] = config.client_secret

    headers = {"Accept": "application/json"}
    if provider == OAuthProvider.GITHUB:
        headers["Accept"] = "application/json"

    async with httpx.AsyncClient() as client:
        token_response = await client.post(
            config.token_url,
            data=token_data,
            headers=headers,
        )

        if token_response.status_code != 200:
            raise HTTPException(status_code=400, detail="Token exchange failed")

        tokens = token_response.json()

        access_token = tokens.get("access_token")
        user_info = {}

        if config.userinfo_url:
            userinfo_response = await client.get(
                config.userinfo_url,
                headers={"Authorization": f"Bearer {access_token}"},
            )
            if userinfo_response.status_code == 200:
                user_data = userinfo_response.json()

                if provider == OAuthProvider.AZURE_AD:
                    user_info = {
                        "sub": user_data.get("id"),
                        "email": user_data.get("mail") or user_data.get("userPrincipalName"),
                        "name": user_data.get("displayName"),
                        "given_name": user_data.get("givenName"),
                        "family_name": user_data.get("surname"),
                        "provider": provider.value,
                    }
                elif provider == OAuthProvider.GITHUB:
                    user_info = {
                        "sub": str(user_data.get("id")),
                        "email": user_data.get("email"),
                        "name": user_data.get("name") or user_data.get("login"),
                        "picture": user_data.get("avatar_url"),
                        "provider": provider.value,
                    }
                else:
                    user_info = {
                        "sub": user_data.get("sub") or user_data.get("id"),
                        "email": user_data.get("email"),
                        "name": user_data.get("name"),
                        "given_name": user_data.get("given_name"),
                        "family_name": user_data.get("family_name"),
                        "picture": user_data.get("picture"),
                        "provider": provider.value,
                    }

    user_info["roles"] = ["user"]

    jwt_token = create_jwt_token(user_info)

    frontend_url = os.getenv("FRONTEND_URL", "http://localhost:3000")
    redirect_url = f"{frontend_url}/auth/callback?token={jwt_token}"

    return RedirectResponse(url=redirect_url)


@router.post("/token", response_model=OAuthTokenResponse)
async def oauth_token_exchange(token_request: OAuthTokenRequest):
    """Exchange authorization code for tokens."""
    state_data = _oauth_states.pop(token_request.state, None)
    if not state_data:
        raise HTTPException(status_code=400, detail="Invalid or expired state")

    config = get_oauth_config(token_request.provider)
    if not config:
        raise HTTPException(status_code=400, detail="Provider not configured")

    import httpx

    token_data = {
        "grant_type": "authorization_code",
        "code": token_request.code,
        "redirect_uri": token_request.redirect_uri or state_data.get("redirect_uri"),
        "client_id": config.client_id,
        "code_verifier": token_request.code_verifier,
    }

    if config.client_secret:
        token_data["client_secret"] = config.client_secret

    async with httpx.AsyncClient() as client:
        response = await client.post(
            config.token_url,
            data=token_data,
            headers={"Accept": "application/json"},
        )

        if response.status_code != 200:
            raise HTTPException(status_code=400, detail="Token exchange failed")

        tokens = response.json()

    return OAuthTokenResponse(
        access_token=tokens.get("access_token"),
        token_type=tokens.get("token_type", "Bearer"),
        expires_in=tokens.get("expires_in", 3600),
        refresh_token=tokens.get("refresh_token"),
        id_token=tokens.get("id_token"),
        scope=tokens.get("scope"),
    )


@router.post("/client-credentials", response_model=OAuthTokenResponse)
async def client_credentials_flow(
    client_id: str,
    client_secret: str,
    scope: str | None = None,
):
    """Client credentials flow for service-to-service auth."""
    valid_client_id = os.getenv("OAUTH_CLIENT_ID")
    valid_client_secret = os.getenv("OAUTH_CLIENT_SECRET")

    if client_id != valid_client_id or client_secret != valid_client_secret:
        raise HTTPException(status_code=401, detail="Invalid client credentials")

    service_info = {
        "sub": client_id,
        "name": client_id,
        "roles": ["service"],
        "provider": "client_credentials",
    }

    token = create_jwt_token(service_info, expires_in=3600)

    return OAuthTokenResponse(
        access_token=token,
        token_type="Bearer",
        expires_in=3600,
        scope=scope or "service",
    )


@router.get("/userinfo", response_model=OAuthUserInfo)
async def get_userinfo(request: Request):
    """Get user information from JWT token."""
    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing or invalid authorization header")

    token = auth_header.split(" ")[1]
    from api.security.jwt_config import get_jwt_secret

    secret = get_jwt_secret()

    try:
        payload = jwt.decode(token, secret, algorithms=["HS256"])
        return OAuthUserInfo(
            sub=payload.get("sub"),
            email=payload.get("email"),
            name=payload.get("name"),
            roles=payload.get("roles", []),
            provider=payload.get("provider", "unknown"),
        )
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")


@router.post("/logout")
async def oauth_logout(request: Request):
    """Logout and invalidate token."""
    auth_header = request.headers.get("Authorization")
    if auth_header and auth_header.startswith("Bearer "):
        token = auth_header.split(" ")[1]
        from api.security.token_revocation import token_revocation_service
        from api.security.jwt_config import get_jwt_secret

        try:
            secret = get_jwt_secret()
            payload = jwt.decode(token, secret, algorithms=["HS256"])
            jti = payload.get("jti")
            if jti:
                await token_revocation_service.revoke_token(jti, reason="logout")
        except Exception:
            pass

    return {"message": "Logged out successfully"}
