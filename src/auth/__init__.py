"""
Authentication Configuration Loader

Loads authentication settings from config/auth.yaml with environment
variable expansion matching the pattern used in config_loader.py.
"""
from pathlib import Path
from typing import Dict, Any, Optional
from pydantic import BaseModel

from ..config_loader import _load_yaml, _expand_env_vars_recursive


class JWTConfig(BaseModel):
    """JWT signing configuration — single source of truth for secrets."""
    secret_key: str
    lifetime_seconds: int = 86400


class SessionConfig(BaseModel):
    """Session middleware configuration (for OIDC state storage)."""
    secret_key: str
    cookie_secure: bool = False


class OIDCConfig(BaseModel):
    """OIDC/OAuth2 SSO configuration."""
    enabled: bool = False
    provider_name: str = "SSO"
    issuer: str = ""
    client_id: str = ""
    client_secret: str = ""
    scopes: list[str] = ["openid", "profile", "email"]
    role_claim: str = "groups"
    role_map: Dict[str, str] = {}
    default_role: str = "viewer"


class RBACConfig(BaseModel):
    """RBAC configuration paths."""
    model_path: str = "config/rbac_model.conf"
    policy_path: str = "config/rbac_policy.csv"


class AuthConfig(BaseModel):
    """Complete authentication configuration."""
    jwt: JWTConfig
    session: SessionConfig
    oidc: OIDCConfig = OIDCConfig()
    rbac: RBACConfig = RBACConfig()


class SeedConfig(BaseModel):
    """Admin seeding configuration."""
    admin_email: str = "admin@coalmine.io"
    admin_password: str = ""
    admin_role: str = "admin"
    admin_display_name: str = "Administrator"


_auth_config_cache: Optional[AuthConfig] = None
_seed_config_cache: Optional[SeedConfig] = None


def get_auth_config() -> AuthConfig:
    """
    Load and cache authentication configuration from config/auth.yaml.
    
    Returns:
        AuthConfig with all settings expanded and validated.
    """
    global _auth_config_cache
    if _auth_config_cache is None:
        raw = _load_yaml("auth.yaml")
        
        # Handle missing auth key
        if "auth" not in raw:
            raw = {"auth": raw}
        
        auth_section = raw.get("auth", {})
        rbac_section = raw.get("rbac", {})
        
        # Expand environment variables
        expanded_auth = _expand_env_vars_recursive(auth_section)
        expanded_rbac = _expand_env_vars_recursive(rbac_section)
        
        # Build config
        config_dict = {
            "jwt": expanded_auth.get("jwt", {}),
            "session": expanded_auth.get("session", {}),
            "oidc": expanded_auth.get("oidc", {}),
            "rbac": expanded_rbac,
        }
        
        _auth_config_cache = AuthConfig(**config_dict)
    
    return _auth_config_cache


def get_seed_config() -> SeedConfig:
    """
    Load and cache seeding configuration from config/auth.yaml (seed section).
    
    Returns:
        SeedConfig with all settings expanded and validated.
    """
    global _seed_config_cache
    if _seed_config_cache is None:
        raw = _load_yaml("auth.yaml")
        auth_section = raw.get("auth", {})
        seed_section = auth_section.get("seed", {})
        expanded = _expand_env_vars_recursive(seed_section)
        _seed_config_cache = SeedConfig(**expanded)
    
    return _seed_config_cache


def reload_auth_config():
    """Force reload of authentication configuration."""
    global _auth_config_cache, _seed_config_cache
    _auth_config_cache = None
    _seed_config_cache = None

