"""
Canary Management API Routes

Provides endpoints for creating, listing, deleting canaries and managing credentials.
"""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime

from ..auth import require_permission, require_scope
from src.services import CanaryService

router = APIRouter(prefix="/canaries")


# =============================================================================
# Schemas
# =============================================================================

class CanaryCreate(BaseModel):
    """Request schema for creating a canary."""
    name: str
    resource_type: str
    account_id: str  # UUID or name of the account
    logging_id: str
    interval: int = 0
    params: Optional[dict] = None


class CanaryResponse(BaseModel):
    """Response schema for canary data."""
    id: str
    name: str
    resource_type: str
    status: str
    account_id: Optional[str] = None
    account_name: Optional[str] = None
    current_resource_id: Optional[str] = None
    expires_at: Optional[datetime] = None
    created_at: Optional[datetime] = None

    @classmethod
    def from_model(cls, canary):
        """Create response from CanaryResource model."""
        return cls(
            id=str(canary.id),
            name=canary.name,
            resource_type=canary.resource_type.value,
            status=canary.status.value,
            account_id=str(canary.account_id) if canary.account_id else None,
            account_name=canary.account.name if canary.account else None,
            current_resource_id=canary.current_resource_id,
            expires_at=canary.expires_at,
            created_at=canary.created_at
        )


class CanaryListResponse(BaseModel):
    """Response schema for list of canaries."""
    canaries: List[CanaryResponse]
    total: int


class CredentialsResponse(BaseModel):
    """Response schema for canary credentials."""
    canary_id: str
    canary_name: str
    credentials: Optional[dict] = None


class TriggerResponse(BaseModel):
    """Response schema for trigger action."""
    success: bool
    message: str


# =============================================================================
# Endpoints
# =============================================================================

@router.post(
    "/",
    response_model=dict,
    dependencies=[
        Depends(require_permission("write")),
        Depends(require_scope("canaries"))
    ],
    summary="Create a new canary resource"
)
async def create_canary(payload: CanaryCreate):
    """
    Queue creation of a new canary resource.
    
    The canary will be created asynchronously via a Celery task.
    """
    with CanaryService() as svc:
        result = svc.create(
            name=payload.name,
            resource_type=payload.resource_type,
            account_id=payload.account_id,
            logging_id=payload.logging_id,
            interval=payload.interval,
            params=payload.params
        )
        
        if not result.success:
            raise HTTPException(status_code=400, detail=result.error)
        
        return result.data


@router.get(
    "/",
    response_model=CanaryListResponse,
    dependencies=[Depends(require_scope("canaries"))],
    summary="List all canaries"
)
async def list_canaries():
    """Retrieve a list of all canary resources."""
    with CanaryService() as svc:
        result = svc.list()
        
        return CanaryListResponse(
            canaries=[CanaryResponse.from_model(c) for c in result.items],
            total=result.total
        )


@router.get(
    "/{canary_id}",
    response_model=CanaryResponse,
    dependencies=[Depends(require_scope("canaries"))],
    summary="Get a specific canary"
)
async def get_canary(canary_id: str):
    """Retrieve details for a specific canary by ID or name."""
    with CanaryService() as svc:
        result = svc.get(canary_id)
        
        if not result.success:
            raise HTTPException(status_code=404, detail=result.error)
        
        return CanaryResponse.from_model(result.data)


@router.delete(
    "/{canary_id}",
    response_model=dict,
    dependencies=[
        Depends(require_permission("write")),
        Depends(require_scope("canaries"))
    ],
    summary="Delete a canary"
)
async def delete_canary(canary_id: str):
    """
    Queue deletion of a canary resource.
    
    The canary will be deleted asynchronously via a Celery task.
    """
    with CanaryService() as svc:
        result = svc.delete(canary_id)
        
        if not result.success:
            raise HTTPException(status_code=404, detail=result.error)
        
        return result.data


@router.get(
    "/{canary_id}/credentials",
    response_model=CredentialsResponse,
    dependencies=[
        Depends(require_permission("read")),
        Depends(require_scope("canaries"))
    ],
    summary="Get canary credentials"
)
async def get_credentials(canary_id: str):
    """Retrieve stored credentials for a canary."""
    with CanaryService() as svc:
        result = svc.get_credentials(canary_id)
        
        if not result.success:
            raise HTTPException(status_code=404, detail=result.error)
        
        return CredentialsResponse(**result.data)


@router.post(
    "/{canary_id}/trigger",
    response_model=TriggerResponse,
    dependencies=[
        Depends(require_permission("write")),
        Depends(require_scope("canaries"))
    ],
    summary="Trigger a test alert for a canary"
)
async def trigger_canary(canary_id: str):
    """
    Execute a trigger action to simulate canary access.
    
    This is useful for testing detection pipelines.
    """
    with CanaryService() as svc:
        result = svc.trigger(canary_id)
        
        if not result.success:
            raise HTTPException(status_code=400, detail=result.error)
        
        return TriggerResponse(**result.data)
