"""
Unit tests for API authentication dependencies.

Tests authentication flows for both API keys and session-based auth.
"""
import pytest
from unittest.mock import patch, MagicMock, AsyncMock
from fastapi import HTTPException


def make_mock_request(cookies=None, path="/api/v1/canaries"):
    """Create a mock FastAPI Request object."""
    mock_request = MagicMock()
    mock_request.cookies = cookies or {}
    mock_request.url = MagicMock()
    mock_request.url.path = path
    return mock_request


class TestGetCurrentAuth:
    """Tests for get_current_auth dependency."""
    
    @pytest.mark.asyncio
    async def test_missing_api_key_and_session_returns_401(self):
        """Test that missing auth returns 401."""
        from src.api.auth import get_current_auth
        
        mock_request = make_mock_request()
        
        with pytest.raises(HTTPException) as exc_info:
            await get_current_auth(request=mock_request, api_key=None)
        
        assert exc_info.value.status_code == 401
        assert "Authentication required" in exc_info.value.detail
    
    @pytest.mark.asyncio
    async def test_invalid_api_key_returns_403(self):
        """Test that invalid API key returns 403."""
        from src.api.auth import get_current_auth
        
        mock_request = make_mock_request()
        
        with patch("src.api.auth.validate_api_key", return_value=None):
            with pytest.raises(HTTPException) as exc_info:
                await get_current_auth(request=mock_request, api_key="invalid-key")
            
            assert exc_info.value.status_code == 403
            assert "Invalid" in exc_info.value.detail
    
    @pytest.mark.asyncio
    async def test_valid_api_key_returns_config(self):
        """Test that valid API key returns its config."""
        from src.api.auth import get_current_auth
        from src.api_keys_loader import ApiKeyConfig
        
        mock_config = ApiKeyConfig(
            key="valid-key",
            permissions=["read", "write"],
            scopes=["all"]
        )
        
        mock_request = make_mock_request()
        
        with patch("src.api.auth.validate_api_key", return_value=mock_config):
            result = await get_current_auth(request=mock_request, api_key="valid-key")
            
            assert result == mock_config
            assert result.permissions == ["read", "write"]


class TestRequirePermission:
    """Tests for require_permission dependency factory."""
    
    @pytest.mark.asyncio
    async def test_missing_permission_returns_403(self):
        """Test that missing permission returns 403."""
        from src.api.auth import require_permission
        from src.api_keys_loader import ApiKeyConfig
        
        mock_config = ApiKeyConfig(
            key="test-key",
            permissions=["read"],  # Only read
            scopes=["all"]
        )
        
        mock_request = make_mock_request()
        
        check_fn = require_permission("write")
        
        with patch("src.api.auth.validate_api_key", return_value=mock_config):
            with pytest.raises(HTTPException) as exc_info:
                await check_fn(request=mock_request, api_key="test-key")
            
            assert exc_info.value.status_code == 403
            assert "write" in exc_info.value.detail.lower()
    
    @pytest.mark.asyncio
    async def test_has_permission_succeeds(self):
        """Test that having permission succeeds."""
        from src.api.auth import require_permission
        from src.api_keys_loader import ApiKeyConfig
        
        mock_config = ApiKeyConfig(
            key="test-key",
            permissions=["read", "write"],
            scopes=["all"]
        )
        
        mock_request = make_mock_request()
        
        check_fn = require_permission("write")
        
        with patch("src.api.auth.validate_api_key", return_value=mock_config):
            result = await check_fn(request=mock_request, api_key="test-key")
            assert result == mock_config


class TestRequireScope:
    """Tests for require_scope dependency factory."""
    
    @pytest.mark.asyncio
    async def test_missing_scope_returns_403(self):
        """Test that missing scope returns 403."""
        from src.api.auth import require_scope
        from src.api_keys_loader import ApiKeyConfig
        
        mock_config = ApiKeyConfig(
            key="test-key",
            permissions=["read"],
            scopes=["canaries"]  # Only canaries
        )
        
        mock_request = make_mock_request()
        
        check_fn = require_scope("alerts")
        
        with patch("src.api.auth.validate_api_key", return_value=mock_config):
            with pytest.raises(HTTPException) as exc_info:
                await check_fn(request=mock_request, api_key="test-key")
            
            assert exc_info.value.status_code == 403
            assert "alerts" in exc_info.value.detail
    
    @pytest.mark.asyncio
    async def test_has_scope_succeeds(self):
        """Test that having scope succeeds."""
        from src.api.auth import require_scope
        from src.api_keys_loader import ApiKeyConfig
        
        mock_config = ApiKeyConfig(
            key="test-key",
            permissions=["read"],
            scopes=["canaries", "alerts"]
        )
        
        mock_request = make_mock_request()
        
        check_fn = require_scope("alerts")
        
        with patch("src.api.auth.validate_api_key", return_value=mock_config):
            result = await check_fn(request=mock_request, api_key="test-key")
            assert result == mock_config
    
    @pytest.mark.asyncio
    async def test_all_scope_allows_everything(self):
        """Test that 'all' scope grants access to everything."""
        from src.api.auth import require_scope
        from src.api_keys_loader import ApiKeyConfig
        
        mock_config = ApiKeyConfig(
            key="test-key",
            permissions=["read"],
            scopes=["all"]
        )
        
        mock_request = make_mock_request()
        
        for scope in ["canaries", "alerts", "credentials", "logging"]:
            check_fn = require_scope(scope)
            with patch("src.api.auth.validate_api_key", return_value=mock_config):
                result = await check_fn(request=mock_request, api_key="test-key")
                assert result == mock_config


class TestRoleBasedAuth:
    """Tests for role-based auth using Casbin."""
    
    @pytest.mark.asyncio
    async def test_session_user_uses_casbin_for_permission(self):
        """Test that JWT-authenticated users have permissions checked via Casbin."""
        import uuid
        from src.api.auth import require_permission, SessionAuth
        
        user_id = uuid.uuid4()
        
        mock_request = make_mock_request(
            cookies={"coalmine_auth": "valid-jwt-token"}
        )
        
        check_fn = require_permission("read")
        
        # Mock JWT decode → user UUID
        with patch("src.api.auth.decode_coalmine_jwt", return_value=user_id):
            # Mock async DB lookup → User object
            mock_user = MagicMock()
            mock_user.email = "testuser@coalmine.io"
            mock_user.role = "viewer"
            mock_user.is_active = True
            mock_user.is_superuser = False
            
            mock_session = AsyncMock()
            mock_result = MagicMock()
            mock_result.unique.return_value.scalar_one_or_none.return_value = mock_user
            mock_session.execute = AsyncMock(return_value=mock_result)
            
            mock_ctx = AsyncMock()
            mock_ctx.__aenter__ = AsyncMock(return_value=mock_session)
            mock_ctx.__aexit__ = AsyncMock(return_value=False)
            
            with patch("src.auth.users.async_session_maker", return_value=mock_ctx):
                with patch("src.api.auth._check_with_casbin", return_value=True):
                    result = await check_fn(request=mock_request, api_key=None)
                    assert isinstance(result, SessionAuth)
                    assert result.username == "testuser@coalmine.io"
                    assert result.role == "viewer"
    
    @pytest.mark.asyncio
    async def test_require_role_admin(self):
        """Test that require_role enforces role hierarchy."""
        import uuid
        from src.api.auth import require_role, SessionAuth
        
        user_id = uuid.uuid4()
        
        mock_request = make_mock_request(
            cookies={"coalmine_auth": "valid-jwt-token"}
        )
        
        check_fn = require_role("admin")
        
        with patch("src.api.auth.decode_coalmine_jwt", return_value=user_id):
            mock_user = MagicMock()
            mock_user.email = "admin@coalmine.io"
            mock_user.role = "admin"
            mock_user.is_active = True
            mock_user.is_superuser = False
            
            mock_session = AsyncMock()
            mock_result = MagicMock()
            mock_result.unique.return_value.scalar_one_or_none.return_value = mock_user
            mock_session.execute = AsyncMock(return_value=mock_result)
            
            mock_ctx = AsyncMock()
            mock_ctx.__aenter__ = AsyncMock(return_value=mock_session)
            mock_ctx.__aexit__ = AsyncMock(return_value=False)
            
            with patch("src.auth.users.async_session_maker", return_value=mock_ctx):
                result = await check_fn(request=mock_request, api_key=None)
                assert result.role == "admin"

