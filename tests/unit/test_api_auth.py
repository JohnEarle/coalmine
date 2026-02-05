"""
Unit tests for API authentication dependencies.
"""
import pytest
from unittest.mock import patch, AsyncMock
from fastapi import HTTPException


class TestGetCurrentKey:
    """Tests for get_current_key dependency."""
    
    @pytest.mark.asyncio
    async def test_missing_api_key_returns_401(self):
        """Test that missing API key returns 401."""
        from src.api.auth import get_current_key
        
        with pytest.raises(HTTPException) as exc_info:
            await get_current_key(api_key=None)
        
        assert exc_info.value.status_code == 401
        assert "Missing" in exc_info.value.detail
    
    @pytest.mark.asyncio
    async def test_invalid_api_key_returns_403(self):
        """Test that invalid API key returns 403."""
        from src.api.auth import get_current_key
        
        with patch("src.api.auth.validate_api_key", return_value=None):
            with pytest.raises(HTTPException) as exc_info:
                await get_current_key(api_key="invalid-key")
            
            assert exc_info.value.status_code == 403
            assert "Invalid" in exc_info.value.detail
    
    @pytest.mark.asyncio
    async def test_valid_api_key_returns_config(self):
        """Test that valid API key returns its config."""
        from src.api.auth import get_current_key
        from src.api_keys_loader import ApiKeyConfig
        
        mock_config = ApiKeyConfig(
            key="valid-key",
            permissions=["read", "write"],
            scopes=["all"]
        )
        
        with patch("src.api.auth.validate_api_key", return_value=mock_config):
            result = await get_current_key(api_key="valid-key")
            
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
        
        check_fn = require_permission("write")
        
        with pytest.raises(HTTPException) as exc_info:
            await check_fn(config=mock_config)
        
        assert exc_info.value.status_code == 403
        assert "write" in exc_info.value.detail
    
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
        
        check_fn = require_permission("write")
        result = await check_fn(config=mock_config)
        
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
        
        check_fn = require_scope("alerts")
        
        with pytest.raises(HTTPException) as exc_info:
            await check_fn(config=mock_config)
        
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
        
        check_fn = require_scope("alerts")
        result = await check_fn(config=mock_config)
        
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
        
        for scope in ["canaries", "alerts", "environments", "logging"]:
            check_fn = require_scope(scope)
            result = await check_fn(config=mock_config)
            assert result == mock_config
