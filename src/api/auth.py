"""
API Authentication Module

Provides FastAPI dependencies for authentication via:
1. API Key (X-API-Key header) - for programmatic access
2. Session Cookie - for WebUI browser access

Both methods are supported transparently - the same routes work with either.
"""
from fastapi import Depends, HTTPException, Security, Request
from fastapi.security import APIKeyHeader
from typing import Callable, Optional, Union
from pydantic import BaseModel

from ..api_keys_loader import validate_api_key, ApiKeyConfig

api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


class SessionAuth(BaseModel):
    """Represents a session-authenticated user with full permissions."""
    username: str
    role: str
    permissions: list[str] = ["read", "write", "admin"]
    scopes: list[str] = ["all"]


# Type alias for either auth method
AuthConfig = Union[ApiKeyConfig, SessionAuth]


def _get_session_user(request: Request) -> Optional[SessionAuth]:
    """
    Check if request has a valid session cookie.
    
    Returns SessionAuth if valid, None otherwise.
    """
    from .session_auth import _session_store, SESSION_COOKIE_NAME
    
    session_id = request.cookies.get(SESSION_COOKIE_NAME)
    if not session_id:
        return None
    
    session = _session_store.get(session_id)
    if not session:
        return None
    
    return SessionAuth(
        username=session["username"],
        role=session["role"]
    )


async def get_current_auth(
    request: Request,
    api_key: str = Security(api_key_header)
) -> AuthConfig:
    """
    Dependency that validates authentication via API key OR session.
    
    Supports both:
    - API Key: X-API-Key header for programmatic access
    - Session: Cookie-based auth for WebUI browser access
    
    Returns:
        ApiKeyConfig or SessionAuth for the authenticated user.
        
    Raises:
        HTTPException: 401 if not authenticated.
    """
    # First try API key
    if api_key:
        config = validate_api_key(api_key)
        if config:
            return config
        raise HTTPException(status_code=403, detail="Invalid API key")
    
    # Then try session auth
    session_user = _get_session_user(request)
    if session_user:
        return session_user
    
    # No valid auth found
    raise HTTPException(
        status_code=401,
        detail="Authentication required (API key or session)",
        headers={"WWW-Authenticate": "ApiKey"}
    )


# Backwards compatibility - alias for existing code
async def get_current_key(
    request: Request,
    api_key: str = Security(api_key_header)
) -> AuthConfig:
    """Backwards-compatible alias for get_current_auth."""
    return await get_current_auth(request, api_key)


def require_permission(permission: str) -> Callable:
    """
    Dependency factory for permission checks.
    
    Args:
        permission: Required permission (read, write, admin).
        
    Returns:
        Dependency function that validates permission.
    """
    async def check_permission(
        request: Request,
        api_key: str = Security(api_key_header)
    ) -> AuthConfig:
        config = await get_current_auth(request, api_key)
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
    
    Args:
        scope: Required scope (canaries, environments, logging, alerts).
        
    Returns:
        Dependency function that validates scope.
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
