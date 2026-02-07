"""
API Authentication Module

Provides FastAPI dependencies for authentication via:
1. API Key (X-API-Key header) - for programmatic access
2. JWT Cookie (coalmine_auth) - for WebUI browser access via fastapi-users

Permission checks use Casbin RBAC when available, falling back to
the permissions defined in the API key config.
"""
import uuid as uuid_module
from typing import Callable, Optional, Union

import jwt
from fastapi import Depends, HTTPException, Security, Request
from fastapi.security import APIKeyHeader
from pydantic import BaseModel

from ..api_keys_loader import validate_api_key, ApiKeyConfig
from ..logging_config import get_logger

logger = get_logger(__name__)

api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


class SessionAuth(BaseModel):
    """Represents a session-authenticated user."""
    username: str
    role: str = "viewer"
    permissions: list[str] = ["read"]
    scopes: list[str] = ["all"]


# Type alias for either auth method
AuthConfig = Union[ApiKeyConfig, SessionAuth]


def _get_client_ip(request: Request) -> Optional[str]:
    """
    Extract client IP from request, handling proxy headers.
    
    Checks X-Forwarded-For and X-Real-IP headers first (for proxied requests),
    then falls back to the direct client IP.
    """
    forwarded_for = request.headers.get("X-Forwarded-For")
    if forwarded_for:
        return forwarded_for.split(",")[0].strip()
    
    real_ip = request.headers.get("X-Real-IP")
    if real_ip:
        return real_ip.strip()
    
    if request.client:
        return request.client.host
    
    return None


def _get_jwt_secret() -> str:
    """Get JWT secret from auth config (single source of truth)."""
    try:
        from ..auth import get_auth_config
        return get_auth_config().jwt.secret_key
    except Exception:
        import os
        return os.getenv("SECRET_KEY", "coalmine-dev-secret-change-in-production")


def decode_coalmine_jwt(cookie: str) -> Optional[uuid_module.UUID]:
    """
    Decode a coalmine_auth JWT cookie and return the user UUID.
    
    Single source of truth for JWT decoding — used by all auth paths.
    Skips audience verification to support fastapi-users tokens.
    
    Returns:
        UUID of the authenticated user, or None if invalid/expired.
    """
    try:
        payload = jwt.decode(
            cookie,
            _get_jwt_secret(),
            algorithms=["HS256"],
            options={"verify_aud": False}
        )
        user_id_str = payload.get("sub")
        if not user_id_str:
            return None
        return uuid_module.UUID(user_id_str)
    except jwt.ExpiredSignatureError:
        logger.debug("JWT cookie expired")
        return None
    except (jwt.InvalidTokenError, ValueError) as e:
        logger.debug(f"Invalid JWT cookie: {e}")
        return None


async def get_current_auth(
    request: Request,
    api_key: str = Security(api_key_header)
) -> AuthConfig:
    """
    Dependency that validates authentication via API key OR JWT cookie.
    
    Resolution order:
    1. API Key (X-API-Key header)
    2. JWT Cookie (coalmine_auth via fastapi-users)
    
    Returns:
        ApiKeyConfig or SessionAuth for the authenticated user.
        
    Raises:
        HTTPException: 401 if not authenticated, 403 if key is invalid.
    """
    # 1. Try API key
    if api_key:
        client_ip = _get_client_ip(request)
        config = validate_api_key(api_key, client_ip=client_ip)
        if config:
            return config
        raise HTTPException(status_code=403, detail="Invalid API key")
    
    # 2. Try JWT cookie
    cookie = request.cookies.get("coalmine_auth")
    if cookie:
        user_id = decode_coalmine_jwt(cookie)
        if user_id:
            try:
                from ..auth.users import async_session_maker
                from ..models import User
                from sqlalchemy import select
                
                async with async_session_maker() as session:
                    result = await session.execute(
                        select(User).where(User.id == user_id)
                    )
                    user = result.unique().scalar_one_or_none()
                    
                    if user and user.is_active:
                        effective_role = "superuser" if user.is_superuser else user.role
                        return SessionAuth(
                            username=user.email,
                            role=effective_role,
                        )
            except Exception as e:
                logger.warning(f"Session validation error: {e}")
    
    # No valid auth found
    raise HTTPException(
        status_code=401,
        detail="Authentication required (API key or session)",
        headers={"WWW-Authenticate": "ApiKey"}
    )


# Backwards compatibility alias
async def get_current_key(
    request: Request,
    api_key: str = Security(api_key_header)
) -> AuthConfig:
    """Backwards-compatible alias for get_current_auth."""
    return await get_current_auth(request, api_key)


def _check_with_casbin(role: str, resource: str, action: str) -> bool:
    """
    Check permission using Casbin if available.
    
    Falls back to None (signal to use legacy check) if Casbin is not configured.
    """
    try:
        from ..auth.rbac import check_permission
        return check_permission(role, resource, action)
    except Exception as e:
        logger.debug(f"Casbin check failed: {e}")
        return None


def require_permission(permission: str) -> Callable:
    """
    Dependency factory for permission checks.
    
    Uses Casbin RBAC for session users, falls back to permission list
    for API keys (which have explicit permissions defined in YAML).
    """
    async def check_permission(
        request: Request,
        api_key: str = Security(api_key_header)
    ) -> AuthConfig:
        config = await get_current_auth(request, api_key)
        
        # For session auth, use Casbin
        if isinstance(config, SessionAuth):
            path_parts = request.url.path.strip("/").split("/")
            resource = path_parts[2] if len(path_parts) > 2 else "unknown"
            
            casbin_result = _check_with_casbin(config.role, resource, permission)
            if casbin_result is not None:
                if not casbin_result:
                    raise HTTPException(
                        status_code=403,
                        detail=f"Role '{config.role}' lacks permission: {permission} on {resource}"
                    )
                return config
        
        # API key permission check
        if permission not in config.permissions:
            raise HTTPException(
                status_code=403,
                detail=f"Missing required permission: {permission}"
            )
        return config
    return check_permission


def require_scope(scope: str) -> Callable:
    """
    Dependency factory for scope checks.
    """
    async def check_scope(
        request: Request,
        api_key: str = Security(api_key_header)
    ) -> AuthConfig:
        config = await get_current_auth(request, api_key)
        if "all" not in config.scopes and scope not in config.scopes:
            raise HTTPException(
                status_code=403,
                detail=f"Missing required scope: {scope}"
            )
        return config
    return check_scope


def require_role(role: str) -> Callable:
    """
    Dependency factory for role-based checks.
    
    Only available for session-authenticated users.
    """
    role_hierarchy = {"superuser": 3, "admin": 2, "operator": 1, "viewer": 0}
    
    async def check_role(
        request: Request,
        api_key: str = Security(api_key_header)
    ) -> AuthConfig:
        config = await get_current_auth(request, api_key)
        
        if not isinstance(config, SessionAuth):
            raise HTTPException(
                status_code=403,
                detail="Role-based access requires session authentication"
            )
        
        user_level = role_hierarchy.get(config.role, 0)
        required_level = role_hierarchy.get(role, 0)
        
        if user_level < required_level:
            raise HTTPException(
                status_code=403,
                detail=f"Requires role '{role}' or higher (you have '{config.role}')"
            )
        return config
    return check_role
