"""
API Authentication Module

Provides FastAPI dependencies for API key validation, permission checks,
and scope enforcement.
"""
from fastapi import Depends, HTTPException, Security
from fastapi.security import APIKeyHeader
from typing import Callable

from ..api_keys_loader import validate_api_key, ApiKeyConfig

api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


async def get_current_key(
    api_key: str = Security(api_key_header)
) -> ApiKeyConfig:
    """
    Dependency that validates the API key from request headers.
    
    Returns:
        ApiKeyConfig for the validated key.
        
    Raises:
        HTTPException: 401 if missing, 403 if invalid.
    """
    if not api_key:
        raise HTTPException(
            status_code=401,
            detail="Missing API key",
            headers={"WWW-Authenticate": "ApiKey"}
        )
    
    config = validate_api_key(api_key)
    if not config:
        raise HTTPException(status_code=403, detail="Invalid API key")
    
    return config


def require_permission(permission: str) -> Callable:
    """
    Dependency factory for permission checks.
    
    Args:
        permission: Required permission (read, write, admin).
        
    Returns:
        Dependency function that validates permission.
    """
    async def check_permission(
        config: ApiKeyConfig = Depends(get_current_key)
    ) -> ApiKeyConfig:
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
        config: ApiKeyConfig = Depends(get_current_key)
    ) -> ApiKeyConfig:
        if "all" not in config.scopes and scope not in config.scopes:
            raise HTTPException(
                status_code=403,
                detail=f"Missing required scope: {scope}"
            )
        return config
    return check_scope
