"""
Unit tests for API key loader functionality.
"""
import pytest
import os
from unittest.mock import patch


class TestApiKeyExpansion:
    """Tests for environment variable expansion in API keys."""
    
    def test_expand_env_var_simple(self):
        """Test simple environment variable expansion."""
        from src.config_loader import _expand_env_var
        
        with patch.dict(os.environ, {"TEST_VAR": "test_value"}):
            result = _expand_env_var("${TEST_VAR}")
            assert result == "test_value"
    
    def test_expand_env_var_with_default(self):
        """Test environment variable with default value."""
        from src.config_loader import _expand_env_var
        
        # Ensure var is not set
        os.environ.pop("MISSING_VAR", None)
        
        result = _expand_env_var("${MISSING_VAR:-default_value}")
        assert result == "default_value"
    
    def test_expand_env_var_required_missing(self):
        """Test that missing required var raises error."""
        from src.config_loader import _expand_env_var
        
        os.environ.pop("REQUIRED_VAR", None)
        
        with pytest.raises(ValueError) as exc_info:
            _expand_env_var("${REQUIRED_VAR:?This is required}")
        
        assert "REQUIRED_VAR" in str(exc_info.value)


class TestApiKeyValidation:
    """Tests for API key validation."""
    
    @patch("src.api_keys_loader._load_yaml")
    def test_validate_valid_key(self, mock_load):
        """Test that a valid API key is validated."""
        from src.api_keys_loader import validate_api_key, reload_api_keys
        
        mock_load.return_value = {
            "api_keys": {
                "test_key": {
                    "key": "valid-api-key-123",
                    "permissions": ["read"],
                    "scopes": ["all"],
                    "description": "Test key"
                }
            }
        }
        
        reload_api_keys()
        result = validate_api_key("valid-api-key-123")
        
        assert result is not None
        assert result.permissions == ["read"]
        assert result.scopes == ["all"]
    
    @patch("src.api_keys_loader._load_yaml")
    def test_validate_invalid_key(self, mock_load):
        """Test that an invalid API key returns None."""
        from src.api_keys_loader import validate_api_key, reload_api_keys
        
        mock_load.return_value = {
            "api_keys": {
                "test_key": {
                    "key": "valid-api-key-123",
                    "permissions": ["read"],
                    "scopes": ["all"],
                    "description": "Test key"
                }
            }
        }
        
        reload_api_keys()
        result = validate_api_key("invalid-key")
        
        assert result is None


class TestApiKeyConfig:
    """Tests for ApiKeyConfig model."""
    
    def test_api_key_config_valid(self):
        """Test valid ApiKeyConfig creation."""
        from src.api_keys_loader import ApiKeyConfig
        
        config = ApiKeyConfig(
            key="test-key",
            permissions=["read", "write"],
            scopes=["canaries", "alerts"]
        )
        
        assert config.key == "test-key"
        assert "read" in config.permissions
        assert "write" in config.permissions
        assert config.description == ""  # Default
    
    def test_api_key_config_with_description(self):
        """Test ApiKeyConfig with description."""
        from src.api_keys_loader import ApiKeyConfig
        
        config = ApiKeyConfig(
            key="test-key",
            permissions=["admin"],
            scopes=["all"],
            description="Admin key for testing"
        )
        
        assert config.description == "Admin key for testing"
