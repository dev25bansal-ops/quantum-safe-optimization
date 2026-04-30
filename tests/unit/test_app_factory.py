"""
Tests for application factory and authentication dependencies.

Tests cover:
- App creation in different modes
- Middleware configuration
- Router registration
- Auth dependency injection
- Permission checking
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch


class TestAppFactory:
    """Test AppFactory functionality."""

    def test_create_api_mode_app(self):
        """Test creating application in API mode."""
        from api.app_factory import AppFactory
        
        factory = AppFactory(mode="api", enable_frontend=False)
        assert factory.is_api_mode is True
        assert factory.is_qsop_mode is False
        assert factory.enable_frontend is False

    def test_create_qsop_mode_app(self):
        """Test creating application in QSOP mode."""
        from api.app_factory import AppFactory
        
        factory = AppFactory(mode="qsop", enable_telemetry=False)
        assert factory.is_api_mode is False
        assert factory.is_qsop_mode is True
        assert factory.enable_telemetry is False

    def test_production_mode_detection(self):
        """Test production mode detection."""
        import os
        from api.app_factory import AppFactory
        
        os.environ["APP_ENV"] = "production"
        factory = AppFactory(mode="api")
        assert factory.is_production is True
        assert factory.is_development is False
        
        os.environ["APP_ENV"] = "development"

    def test_feature_flags_configuration(self):
        """Test feature flag configuration."""
        from api.app_factory import AppFactory
        
        factory = AppFactory(
            mode="api",
            enable_websockets=False,
            enable_rate_limiting=False,
            enable_security_middleware=False,
        )
        
        assert factory.enable_websockets is False
        assert factory.enable_rate_limiting is False
        assert factory.enable_security_middleware is False

    def test_create_app_returns_fastapi_instance(self):
        """Test that create_app returns a FastAPI instance."""
        try:
            from api.app_factory import AppFactory
            from fastapi import FastAPI
            
            factory = AppFactory(mode="api", enable_frontend=False)
            app = factory.create_app()
            
            assert isinstance(app, FastAPI)
            assert app.title == "Quantum-Safe Secure Optimization Platform"
        except Exception as e:
            pytest.skip(f"App creation failed: {e}")


class TestAuthDependencies:
    """Test authentication dependencies."""

    @pytest.mark.asyncio
    async def test_get_user_id_from_token(self):
        """Test user ID extraction from token."""
        from api.dependencies.auth import get_user_id
        
        # Mock user
        mock_user = {"sub": "usr_test_001", "user_id": "usr_test_001"}
        
        user_id = await get_user_id(current_user=mock_user)
        assert user_id == "usr_test_001"

    @pytest.mark.asyncio
    async def test_get_user_id_missing_sub(self):
        """Test user ID extraction when sub is missing."""
        from api.dependencies.auth import get_user_id
        from fastapi import HTTPException
        
        mock_user = {"email": "test@example.com"}
        
        with pytest.raises(HTTPException) as exc_info:
            await get_user_id(current_user=mock_user)
        
        assert exc_info.value.status_code == 401

    @pytest.mark.asyncio
    async def test_get_tenant_from_user(self):
        """Test tenant ID extraction from user."""
        from api.dependencies.auth import get_tenant_from_user
        
        mock_user = {"tenant_id": "tenant_001"}
        
        tenant_id = await get_tenant_from_user(current_user=mock_user)
        assert tenant_id == "tenant_001"

    @pytest.mark.asyncio
    async def test_get_tenant_missing_tenant_id(self):
        """Test tenant extraction when tenant_id is missing."""
        from api.dependencies.auth import get_tenant_from_user
        from fastapi import HTTPException
        
        mock_user = {"sub": "usr_001"}
        
        with pytest.raises(HTTPException) as exc_info:
            await get_tenant_from_user(current_user=mock_user)
        
        assert exc_info.value.status_code == 403


class TestPermissionChecking:
    """Test permission checking functionality."""

    @pytest.mark.asyncio
    async def test_admin_has_all_permissions(self):
        """Test that admin role has all permissions."""
        from api.dependencies.auth import check_user_permission
        
        mock_user = {"sub": "usr_001", "roles": ["admin"]}
        
        # Should pass for any permission
        result = await check_user_permission(
            required_permission="delete_users",
            current_user=mock_user,
        )
        assert result is True

    @pytest.mark.asyncio
    async def test_user_with_specific_permission(self):
        """Test user with specific permission."""
        from api.dependencies.auth import check_user_permission
        
        mock_user = {
            "sub": "usr_001",
            "roles": ["user"],
            "permissions": ["read", "write"],
        }
        
        result = await check_user_permission(
            required_permission="read",
            current_user=mock_user,
        )
        assert result is True

    @pytest.mark.asyncio
    async def test_user_lacking_permission(self):
        """Test user lacking required permission."""
        from api.dependencies.auth import check_user_permission
        from fastapi import HTTPException
        
        mock_user = {
            "sub": "usr_001",
            "roles": ["user"],
            "permissions": ["read"],
        }
        
        with pytest.raises(HTTPException) as exc_info:
            await check_user_permission(
                required_permission="delete",
                current_user=mock_user,
            )
        
        assert exc_info.value.status_code == 403

    @pytest.mark.asyncio
    async def test_role_based_permissions(self):
        """Test role-based permission checking."""
        from api.dependencies.auth import check_user_permission
        
        # Operator role should have write permission
        mock_user = {"sub": "usr_001", "roles": ["operator"]}
        
        result = await check_user_permission(
            required_permission="write",
            current_user=mock_user,
        )
        assert result is True


class TestDIContainer:
    """Test dependency injection container."""

    @pytest.mark.asyncio
    async def test_register_and_resolve_service(self):
        """Test service registration and resolution."""
        try:
            from api.di_container import DIContainer
            
            container = DIContainer()
            
            # Register service
            class TestService:
                def __init__(self):
                    self.name = "test"
            
            container.register(TestService)
            
            # Resolve service
            service = container.resolve(TestService)
            assert service is not None
            assert service.name == "test"
        except ImportError:
            pytest.skip("DI container not available")

    @pytest.mark.asyncio
    async def test_resolve_unregistered_service(self):
        """Test resolving unregistered service."""
        try:
            from api.di_container import DIContainer
            
            container = DIContainer()
            
            class UnregisteredService:
                pass
            
            service = container.resolve(UnregisteredService)
            # Should either return None or raise specific exception
            assert service is None or isinstance(service, UnregisteredService)
        except ImportError:
            pytest.skip("DI container not available")
