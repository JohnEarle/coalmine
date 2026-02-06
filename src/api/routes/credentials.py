"""
Credential Management API Routes

Provides endpoints for managing cloud credentials.
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime

from ..auth import require_permission, require_scope
from src.services import CredentialService

router = APIRouter(prefix="/credentials")


# =============================================================================
# Schemas
# =============================================================================

class CredentialCreate(BaseModel):
    """Request schema for creating a credential."""
    name: str
    provider: str
    auth_type: str = "STATIC"
    secrets: Optional[dict] = None
    discovery_config: Optional[dict] = None


class CredentialResponse(BaseModel):
    """Response schema for credential data."""
    id: str
    name: str
    provider: str
    auth_type: str
    status: str
    created_at: Optional[datetime] = None
    account_count: int = 0

    class Config:
        from_attributes = True
    
    @classmethod
    def from_model(cls, cred):
        """Create response from Credential model."""
        return cls(
            id=str(cred.id),
            name=cred.name,
            provider=cred.provider,
            auth_type=cred.auth_type.value if cred.auth_type else "UNKNOWN",
            status=cred.status.value if cred.status else "UNKNOWN",
            created_at=cred.created_at,
            account_count=len(cred.accounts) if cred.accounts else 0
        )


class CredentialListResponse(BaseModel):
    """Response schema for list of credentials."""
    credentials: List[CredentialResponse]
    total: int


class CredentialUpdate(BaseModel):
    """Request schema for updating a credential."""
    auth_type: Optional[str] = None
    secrets: Optional[dict] = None
    discovery_config: Optional[dict] = None


# =============================================================================
# Endpoints
# =============================================================================

@router.post(
    "/",
    response_model=CredentialResponse,
    dependencies=[
        Depends(require_permission("write")),
        Depends(require_scope("environments"))
    ],
    summary="Create a new credential"
)
async def create_credential(payload: CredentialCreate):
    """
    Create a new cloud credential.
    
    Credentials are reusable authentication sources that can access
    one or more cloud accounts.
    """
    with CredentialService() as svc:
        result = svc.create(
            name=payload.name,
            provider=payload.provider,
            auth_type=payload.auth_type,
            secrets=payload.secrets,
            discovery_config=payload.discovery_config
        )
        
        if not result.success:
            raise HTTPException(status_code=400, detail=result.error)
        
        return CredentialResponse.from_model(result.data)


@router.get(
    "/",
    response_model=CredentialListResponse,
    dependencies=[Depends(require_scope("environments"))],
    summary="List all credentials"
)
async def list_credentials():
    """Retrieve a list of all credentials."""
    with CredentialService() as svc:
        result = svc.list()
        
        return CredentialListResponse(
            credentials=[CredentialResponse.from_model(c) for c in result.items],
            total=result.total
        )


@router.get(
    "/{cred_id}",
    response_model=CredentialResponse,
    dependencies=[Depends(require_scope("environments"))],
    summary="Get a specific credential"
)
async def get_credential(cred_id: str):
    """Retrieve details for a specific credential by ID or name."""
    with CredentialService() as svc:
        result = svc.get(cred_id)
        
        if not result.success:
            raise HTTPException(status_code=404, detail=result.error)
        
        return CredentialResponse.from_model(result.data)


@router.patch(
    "/{cred_id}",
    response_model=CredentialResponse,
    dependencies=[
        Depends(require_permission("write")),
        Depends(require_scope("environments"))
    ],
    summary="Update a credential"
)
async def update_credential(cred_id: str, payload: CredentialUpdate):
    """
    Update an existing credential.
    
    Only specified fields will be updated.
    """
    with CredentialService() as svc:
        result = svc.update(
            identifier=cred_id,
            auth_type=payload.auth_type,
            secrets=payload.secrets,
            discovery_config=payload.discovery_config
        )
        
        if not result.success:
            raise HTTPException(status_code=400, detail=result.error)
        
        return CredentialResponse.from_model(result.data)


@router.delete(
    "/{cred_id}",
    dependencies=[
        Depends(require_permission("write")),
        Depends(require_scope("environments"))
    ],
    summary="Delete a credential"
)
async def delete_credential(cred_id: str, force: bool = Query(False)):
    """
    Delete a credential.
    
    Will fail if any accounts are using this credential unless force=true.
    """
    with CredentialService() as svc:
        result = svc.delete(cred_id, force=force)
        
        if not result.success:
            raise HTTPException(status_code=400, detail=result.error)
        
        return {"status": "deleted"}


@router.get(
    "/{cred_id}/validate",
    dependencies=[Depends(require_scope("environments"))],
    summary="Validate credential health"
)
async def validate_credential(cred_id: str):
    """Validate that the credential is accessible and healthy."""
    with CredentialService() as svc:
        result = svc.validate(cred_id)
        
        if not result.success:
            raise HTTPException(status_code=404, detail=result.error)
        
        is_healthy, message = result.data
        return {
            "healthy": is_healthy,
            "message": message
        }


# =============================================================================
# Discovery Endpoints
# =============================================================================

class DiscoveryResponse(BaseModel):
    """Response schema for discovery results."""
    credential_name: str
    discovered: int
    created: int
    skipped: int
    accounts: List[dict]


@router.post(
    "/{cred_id}/discover",
    response_model=DiscoveryResponse,
    dependencies=[
        Depends(require_permission("write")),
        Depends(require_scope("environments"))
    ],
    summary="Discover accounts from credential"
)
async def discover_accounts(cred_id: str):
    """
    Trigger account discovery for an organization-scoped credential.
    
    Discovers all accounts accessible by this credential and creates
    Account records for any that don't already exist.
    """
    with CredentialService() as svc:
        result = svc.discover_accounts(cred_id)
        
        if not result.success:
            raise HTTPException(status_code=400, detail=result.error)
        
        return DiscoveryResponse(**result.data)


class DiscoverableAccount(BaseModel):
    """Account available for discovery."""
    account_id: str
    name: str
    metadata: dict
    already_exists: bool


class DiscoveryPreviewResponse(BaseModel):
    """Response for discovery preview."""
    credential_name: str
    provider: str
    accounts: List[DiscoverableAccount]
    total: int
    error: Optional[str] = None
    message: Optional[str] = None


@router.get(
    "/{cred_id}/discoverable",
    response_model=DiscoveryPreviewResponse,
    dependencies=[Depends(require_scope("environments"))],
    summary="Preview discoverable accounts"
)
async def preview_discoverable_accounts(cred_id: str):
    """
    Preview accounts that can be discovered from an organization credential.
    
    This is a read-only operation - no accounts are created.
    Used by the WebUI to show selectable accounts during account creation.
    """
    with CredentialService() as svc:
        result = svc.preview_discoverable_accounts(cred_id)
        
        if not result.success:
            raise HTTPException(status_code=404, detail=result.error)
        
        return DiscoveryPreviewResponse(
            credential_name=result.data["credential_name"],
            provider=result.data["provider"],
            accounts=[DiscoverableAccount(**a) for a in result.data["accounts"]],
            total=result.data["total"],
            error=result.data.get("error"),
            message=result.data.get("message")
        )


@router.post(
    "/sync",
    dependencies=[
        Depends(require_permission("write")),
        Depends(require_scope("environments"))
    ],
    summary="Sync credentials from YAML config"
)
async def sync_credentials(
    dry_run: bool = Query(False, description="Preview changes without applying"),
    force: bool = Query(False, description="Overwrite existing DB entries")
):
    """
    Synchronize credentials from config/credentials.yaml to the database.
    """
    with CredentialService() as svc:
        result = svc.sync(dry_run=dry_run, force=force)
        
        if not result.success:
            raise HTTPException(status_code=400, detail=result.error)
        
        return result.data
