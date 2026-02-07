"""
API Keys Configuration Loader

Loads API key configurations from config/api_keys.yaml with environment
variable expansion matching the pattern used in config_loader.py.

Enhanced with:
- Key expiration (expires_at)
- IP allowlisting (ip_allowlist)
- User-tied keys (owner)
"""
from datetime import datetime, timezone
from typing import Dict, Optional, List
from ipaddress import ip_address, ip_network
from pydantic import BaseModel, Field
from .config_loader import _load_yaml, _expand_env_vars_recursive
from .logging_config import get_logger

logger = get_logger(__name__)


class ApiKeyConfig(BaseModel):
    """Configuration for a single API key."""
    key: str
    permissions: List[str]  # read, write, admin
    scopes: List[str]       # canaries, credentials, accounts, logging, alerts, all
    description: str = ""
    
    # Enhanced features
    expires_at: Optional[str] = None  # ISO 8601 datetime, None = never expires
    ip_allowlist: List[str] = Field(default_factory=list)  # CIDR blocks, empty = allow all
    owner: Optional[str] = None  # Username for user-tied keys


class ApiKeyValidationResult(BaseModel):
    """Result of API key validation with context."""
    config: Optional[ApiKeyConfig] = None
    valid: bool = False
    error: Optional[str] = None


_api_keys_cache: Optional[Dict[str, ApiKeyConfig]] = None


def get_api_keys() -> Dict[str, ApiKeyConfig]:
    """
    Load and cache API keys from config/api_keys.yaml.
    
    Keys with unresolvable env vars are skipped (logged as warnings)
    rather than crashing the entire auth system.
    
    Returns:
        Dict mapping key names to their ApiKeyConfig.
    """
    global _api_keys_cache
    if _api_keys_cache is None:
        raw = _load_yaml("api_keys.yaml")
        raw_keys = raw.get("api_keys", {})
        _api_keys_cache = {}
        for name, cfg in raw_keys.items():
            try:
                expanded = _expand_env_vars_recursive(cfg)
                _api_keys_cache[name] = ApiKeyConfig(**expanded)
            except (ValueError, KeyError) as e:
                logger.warning(f"Skipping API key '{name}': {e}")
    return _api_keys_cache


def _check_ip_allowed(client_ip: str, allowlist: List[str]) -> bool:
    """
    Check if client IP is in the allowlist.
    
    Args:
        client_ip: Client IP address string
        allowlist: List of CIDR blocks or IPs
        
    Returns:
        True if allowed (or allowlist is empty), False otherwise.
    """
    if not allowlist:
        return True  # Empty allowlist = allow all
    
    try:
        client = ip_address(client_ip)
        for entry in allowlist:
            try:
                # Try as network (CIDR)
                if "/" in entry:
                    network = ip_network(entry, strict=False)
                    if client in network:
                        return True
                else:
                    # Try as single IP
                    if client == ip_address(entry):
                        return True
            except ValueError:
                logger.warning(f"Invalid IP allowlist entry: {entry}")
                continue
        return False
    except ValueError:
        logger.warning(f"Invalid client IP address: {client_ip}")
        return False


def _check_expiration(expires_at: Optional[str]) -> bool:
    """
    Check if key has expired.
    
    Args:
        expires_at: ISO 8601 datetime string or None
        
    Returns:
        True if valid (not expired), False if expired.
    """
    if not expires_at:
        return True  # No expiration = always valid
    
    try:
        # Parse ISO 8601 datetime
        expiry = datetime.fromisoformat(expires_at.replace("Z", "+00:00"))
        now = datetime.now(timezone.utc)
        return now < expiry
    except (ValueError, AttributeError) as e:
        logger.warning(f"Invalid expiration format '{expires_at}': {e}")
        return True  # Invalid format = treat as no expiration


def validate_api_key(
    key: str,
    client_ip: Optional[str] = None
) -> Optional[ApiKeyConfig]:
    """
    Validate an API key and return its configuration.
    
    Checks:
    - Key exists and matches
    - Key has not expired
    - Client IP is in allowlist (if specified)
    
    Args:
        key: The API key string to validate.
        client_ip: Optional client IP for allowlist checking.
        
    Returns:
        ApiKeyConfig if valid, None otherwise.
    """
    for name, config in get_api_keys().items():
        if config.key == key:
            # Check expiration
            if not _check_expiration(config.expires_at):
                logger.warning(f"API key '{name}' has expired")
                return None
            
            # Check IP allowlist
            if client_ip and not _check_ip_allowed(client_ip, config.ip_allowlist):
                logger.warning(f"API key '{name}' blocked for IP {client_ip}")
                return None
            
            return config
    
    return None


def validate_api_key_detailed(
    key: str,
    client_ip: Optional[str] = None
) -> ApiKeyValidationResult:
    """
    Validate an API key with detailed error information.
    
    Returns:
        ApiKeyValidationResult with config, validity, and error details.
    """
    for name, config in get_api_keys().items():
        if config.key == key:
            # Check expiration
            if not _check_expiration(config.expires_at):
                return ApiKeyValidationResult(
                    config=config,
                    valid=False,
                    error=f"API key '{name}' has expired"
                )
            
            # Check IP allowlist
            if client_ip and not _check_ip_allowed(client_ip, config.ip_allowlist):
                return ApiKeyValidationResult(
                    config=config,
                    valid=False,
                    error=f"API key '{name}' not allowed from IP {client_ip}"
                )
            
            return ApiKeyValidationResult(
                config=config,
                valid=True
            )
    
    return ApiKeyValidationResult(
        valid=False,
        error="Invalid API key"
    )


def get_user_api_keys(username: str) -> Dict[str, ApiKeyConfig]:
    """
    Get all API keys owned by a specific user.
    
    Args:
        username: The owner username to filter by.
        
    Returns:
        Dict of key names to configs for keys owned by this user.
    """
    return {
        name: config
        for name, config in get_api_keys().items()
        if config.owner == username
    }


def reload_api_keys():
    """Force reload of API keys configuration."""
    global _api_keys_cache
    _api_keys_cache = None
