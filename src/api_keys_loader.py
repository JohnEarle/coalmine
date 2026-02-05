"""
API Keys Configuration Loader

Loads API key configurations from config/api_keys.yaml with environment
variable expansion matching the pattern used in config_loader.py.
"""
from typing import Dict, Optional, List
from pydantic import BaseModel
from .config_loader import _load_yaml, _expand_env_vars_recursive, reload_configs

class ApiKeyConfig(BaseModel):
    """Configuration for a single API key."""
    key: str
    permissions: List[str]  # read, write, admin
    scopes: List[str]       # canaries, environments, logging, alerts, all
    description: str = ""

_api_keys_cache: Optional[Dict[str, ApiKeyConfig]] = None


def get_api_keys() -> Dict[str, ApiKeyConfig]:
    """
    Load and cache API keys from config/api_keys.yaml.
    
    Returns:
        Dict mapping key names to their ApiKeyConfig.
    """
    global _api_keys_cache
    if _api_keys_cache is None:
        raw = _load_yaml("api_keys.yaml")
        raw_keys = raw.get("api_keys", {})
        expanded = _expand_env_vars_recursive(raw_keys)
        _api_keys_cache = {
            name: ApiKeyConfig(**cfg) for name, cfg in expanded.items()
        }
    return _api_keys_cache


def validate_api_key(key: str) -> Optional[ApiKeyConfig]:
    """
    Validate an API key and return its configuration.
    
    Args:
        key: The API key string to validate.
        
    Returns:
        ApiKeyConfig if valid, None otherwise.
    """
    for config in get_api_keys().values():
        if config.key == key:
            return config
    return None


def reload_api_keys():
    """Force reload of API keys configuration."""
    global _api_keys_cache
    _api_keys_cache = None
