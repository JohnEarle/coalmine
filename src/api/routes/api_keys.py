"""
API Key Management Routes

Thin API layer over AuthService for API key CRUD operations.
"""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Optional, List

from ...services import AuthService
from ..auth import require_permission, require_role, SessionAuth, AuthConfig

router = APIRouter(prefix="/api-keys", tags=["api-keys"])


class ApiKeyInfo(BaseModel):
    """API key information (without exposing the actual key)."""
    name: str
    description: str
    permissions: List[str]
    scopes: List[str]
    expires_at: Optional[str] = None
    has_ip_allowlist: bool = False
    owner: Optional[str] = None
    is_active: bool = True


class ApiKeyListResponse(BaseModel):
    """Response for listing API keys."""
    keys: List[ApiKeyInfo]
    total: int


class CreateApiKeyRequest(BaseModel):
    """Request to create a new API key."""
    name: str
    permissions: List[str]
    scopes: List[str]
    description: str = ""
    expires_at: Optional[str] = None
    ip_allowlist: Optional[List[str]] = None
    owner: Optional[str] = None


class CreateApiKeyResponse(BaseModel):
    """Response containing the newly created key (shown only once)."""
    name: str
    key: str
    message: str


class CreateMyApiKeyRequest(BaseModel):
    """Request to create a personal API key."""
    name: str
    permissions: List[str]
    scopes: List[str]
    description: str = ""
    expires_at: Optional[str] = None


def _svc_to_response(result) -> ApiKeyListResponse:
    """Convert AuthService ListResult to API response."""
    return ApiKeyListResponse(
        keys=[
            ApiKeyInfo(
                name=k.name,
                description=k.description,
                permissions=k.permissions,
                scopes=k.scopes,
                expires_at=k.expires_at,
                has_ip_allowlist=k.has_ip_allowlist,
                owner=k.owner,
                is_active=k.is_active,
            )
            for k in result.items
        ],
        total=result.total
    )


# =========================================================================
# Self-Service Endpoints (/me) — registered FIRST to avoid /{key_name}
# matching "me" as a key name.
# =========================================================================

@router.get("/me", response_model=ApiKeyListResponse)
async def list_my_api_keys(
    auth: AuthConfig = Depends(require_permission("read"))
):
    """List API keys owned by the current session user."""
    if not isinstance(auth, SessionAuth):
        return ApiKeyListResponse(keys=[], total=0)

    with AuthService() as svc:
        result = svc.list_user_api_keys(auth.username)
    return _svc_to_response(result)


@router.post("/me", response_model=CreateApiKeyResponse)
async def create_my_api_key(
    request: CreateMyApiKeyRequest,
    auth: AuthConfig = Depends(require_permission("read"))
):
    """Create an API key for yourself (self-service)."""
    if not isinstance(auth, SessionAuth):
        raise HTTPException(
            status_code=400,
            detail="Self-service key creation requires session authentication"
        )

    key_name = f"{auth.username}_{request.name}"

    with AuthService() as svc:
        result = svc.create_api_key(
            name=key_name,
            permissions=request.permissions,
            scopes=request.scopes,
            description=request.description,
            expires_at=request.expires_at,
            owner=auth.username
        )

        if not result.success:
            raise HTTPException(status_code=400, detail=result.error)

        return CreateApiKeyResponse(
            name=result.data["name"],
            key=result.data["key"],
            message=result.data["message"]
        )


@router.delete("/me/{key_name}")
async def revoke_my_api_key(
    key_name: str,
    auth: AuthConfig = Depends(require_permission("read"))
):
    """Revoke your own API key (self-service)."""
    if not isinstance(auth, SessionAuth):
        raise HTTPException(
            status_code=400,
            detail="Self-service key revocation requires session authentication"
        )

    with AuthService() as svc:
        user_keys = svc.list_user_api_keys(auth.username)
        user_key_names = [k.name for k in user_keys.items]

        if key_name not in user_key_names:
            raise HTTPException(
                status_code=404,
                detail=f"API key '{key_name}' not found or not owned by you"
            )

        result = svc.revoke_api_key(key_name)

        if not result.success:
            raise HTTPException(status_code=400, detail=result.error)

        return {"status": "revoked", "name": key_name}


# =========================================================================
# Admin Endpoints — after /me so /{key_name} doesn't shadow it
# =========================================================================

@router.get("", response_model=ApiKeyListResponse)
async def list_api_keys(
    auth: AuthConfig = Depends(require_role("admin"))
):
    """List all configured API keys (admin only)."""
    with AuthService() as svc:
        result = svc.list_api_keys()
    return _svc_to_response(result)


@router.post("", response_model=CreateApiKeyResponse)
async def create_api_key(
    request: CreateApiKeyRequest,
    auth: AuthConfig = Depends(require_role("admin"))
):
    """Create a new API key (admin only). Returns key ONCE."""
    with AuthService() as svc:
        result = svc.create_api_key(
            name=request.name,
            permissions=request.permissions,
            scopes=request.scopes,
            description=request.description,
            expires_at=request.expires_at,
            ip_allowlist=request.ip_allowlist,
            owner=request.owner
        )

        if not result.success:
            raise HTTPException(status_code=400, detail=result.error)

        return CreateApiKeyResponse(
            name=result.data["name"],
            key=result.data["key"],
            message=result.data["message"]
        )


@router.get("/{key_name}", response_model=ApiKeyInfo)
async def get_api_key(
    key_name: str,
    auth: AuthConfig = Depends(require_role("admin"))
):
    """Get details for a specific API key (admin only)."""
    with AuthService() as svc:
        result = svc.list_api_keys()

    for k in result.items:
        if k.name == key_name:
            return ApiKeyInfo(
                name=k.name,
                description=k.description,
                permissions=k.permissions,
                scopes=k.scopes,
                expires_at=k.expires_at,
                has_ip_allowlist=k.has_ip_allowlist,
                owner=k.owner,
                is_active=k.is_active,
            )

    raise HTTPException(status_code=404, detail=f"API key '{key_name}' not found")


@router.delete("/{key_name}")
async def revoke_api_key(
    key_name: str,
    auth: AuthConfig = Depends(require_role("admin"))
):
    """Revoke (delete) an API key (admin only)."""
    with AuthService() as svc:
        result = svc.revoke_api_key(key_name)

        if not result.success:
            raise HTTPException(status_code=404, detail=result.error)

        return {"status": "revoked", "name": key_name}
