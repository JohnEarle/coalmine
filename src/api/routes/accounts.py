"""
Account Management API Routes

Provides endpoints for managing cloud accounts (deployment targets).
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime

from ..auth import require_permission, require_scope
from src.services import AccountService

router = APIRouter(prefix="/accounts")


# =============================================================================
# Schemas
# =============================================================================

class AccountCreate(BaseModel):
    """Request schema for creating an account."""
    name: str
    credential_id: str  # UUID of the credential
    account_id: str  # AWS account ID or GCP project ID
    role_override: Optional[str] = None
    metadata: Optional[dict] = None


class AccountResponse(BaseModel):
    """Response schema for account data."""
    id: str
    name: str
    credential_id: str
    credential_name: str
    account_id: str
    provider: str
    source: str
    role_override: Optional[str] = None
    is_enabled: bool
    status: str
    metadata: Optional[dict] = None
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True
    
    @classmethod
    def from_model(cls, account):
        """Create response from Account model."""
        return cls(
            id=str(account.id),
            name=account.name,
            credential_id=str(account.credential_id),
            credential_name=account.credential.name if account.credential else "N/A",
            account_id=account.account_id,
            provider=account.credential.provider if account.credential else "UNKNOWN",
            source=account.source.value if account.source else "MANUAL",
            role_override=account.role_override,
            is_enabled=account.is_enabled == "true",
            status=account.status.value if account.status else "UNKNOWN",
            metadata=account.account_metadata,
            created_at=account.created_at
        )


class AccountListResponse(BaseModel):
    """Response schema for list of accounts."""
    accounts: List[AccountResponse]
    total: int


class AccountUpdate(BaseModel):
    """Request schema for updating an account."""
    is_enabled: Optional[bool] = None
    role_override: Optional[str] = None
    metadata: Optional[dict] = None


# =============================================================================
# Endpoints
# =============================================================================

@router.post(
    "/",
    response_model=AccountResponse,
    dependencies=[
        Depends(require_permission("write")),
        Depends(require_scope("environments"))
    ],
    summary="Create a new account"
)
async def create_account(payload: AccountCreate):
    """
    Manually create a cloud account (deployment target).
    
    Accounts reference a credential for authentication.
    """
    with AccountService() as svc:
        result = svc.create(
            name=payload.name,
            credential_id=payload.credential_id,
            account_id=payload.account_id,
            role_override=payload.role_override,
            metadata=payload.metadata
        )
        
        if not result.success:
            raise HTTPException(status_code=400, detail=result.error)
        
        return AccountResponse.from_model(result.data)


@router.get(
    "/",
    response_model=AccountListResponse,
    dependencies=[Depends(require_scope("environments"))],
    summary="List all accounts"
)
async def list_accounts(
    credential: Optional[str] = Query(None, description="Filter by credential name or ID"),
    provider: Optional[str] = Query(None, description="Filter by provider (AWS, GCP)")
):
    """Retrieve a list of all cloud accounts."""
    with AccountService() as svc:
        result = svc.list(credential=credential, provider=provider)
        
        return AccountListResponse(
            accounts=[AccountResponse.from_model(a) for a in result.items],
            total=result.total
        )


@router.get(
    "/{account_id}",
    response_model=AccountResponse,
    dependencies=[Depends(require_scope("environments"))],
    summary="Get a specific account"
)
async def get_account(account_id: str):
    """Retrieve details for a specific account by ID or name."""
    with AccountService() as svc:
        result = svc.get(account_id)
        
        if not result.success:
            raise HTTPException(status_code=404, detail=result.error)
        
        return AccountResponse.from_model(result.data)


@router.patch(
    "/{account_id}",
    response_model=AccountResponse,
    dependencies=[
        Depends(require_permission("write")),
        Depends(require_scope("environments"))
    ],
    summary="Update an account"
)
async def update_account(account_id: str, payload: AccountUpdate):
    """Update account settings (enable/disable, role override, metadata)."""
    with AccountService() as svc:
        result = svc.update(
            identifier=account_id,
            is_enabled=payload.is_enabled,
            role_override=payload.role_override,
            metadata=payload.metadata
        )
        
        if not result.success:
            raise HTTPException(status_code=404, detail=result.error)
        
        return AccountResponse.from_model(result.data)


@router.delete(
    "/{account_id}",
    dependencies=[
        Depends(require_permission("write")),
        Depends(require_scope("environments"))
    ],
    summary="Delete an account"
)
async def delete_account(account_id: str):
    """
    Delete a cloud account.
    
    Will fail if any canaries are deployed to this account.
    """
    with AccountService() as svc:
        result = svc.delete(account_id)
        
        if not result.success:
            raise HTTPException(status_code=400, detail=result.error)
        
        return {"status": "deleted"}


@router.get(
    "/{account_id}/validate",
    dependencies=[Depends(require_scope("environments"))],
    summary="Validate account health"
)
async def validate_account(account_id: str):
    """Validate that the account is accessible and healthy."""
    with AccountService() as svc:
        result = svc.validate(account_id)
        
        if not result.success:
            raise HTTPException(status_code=404, detail=result.error)
        
        is_healthy, message = result.data
        return {
            "healthy": is_healthy,
            "message": message
        }
