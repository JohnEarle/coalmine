"""
Logging Resource Management API Routes

Provides endpoints for managing logging resources (CloudTrail, GCP Audit Sink, etc.)
"""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime

from ..auth import require_permission, require_scope
from src.services import LoggingResourceService

router = APIRouter(prefix="/logging-resources")


# =============================================================================
# Schemas
# =============================================================================

class LoggingResourceCreate(BaseModel):
    """Request schema for creating a logging resource."""
    name: str
    provider_type: str
    account_id: str  # UUID or name of the account
    config: Optional[dict] = None


class LoggingResourceResponse(BaseModel):
    """Response schema for logging resource data."""
    id: str
    name: str
    provider_type: str
    account_id: Optional[str] = None
    account_name: Optional[str] = None
    status: str
    created_at: Optional[datetime] = None

    @classmethod
    def from_model(cls, resource):
        """Create response from LoggingResource model."""
        return cls(
            id=str(resource.id),
            name=resource.name,
            provider_type=resource.provider_type.value,
            account_id=str(resource.account_id) if resource.account_id else None,
            account_name=resource.account.name if resource.account else None,
            status=resource.status.value if resource.status else "UNKNOWN",
            created_at=resource.created_at
        )


class LoggingResourceListResponse(BaseModel):
    """Response schema for list of logging resources."""
    logging_resources: List[LoggingResourceResponse]
    total: int


# =============================================================================
# Endpoints
# =============================================================================

@router.post(
    "/",
    response_model=dict,
    dependencies=[
        Depends(require_permission("write")),
        Depends(require_scope("logging"))
    ],
    summary="Create a new logging resource"
)
async def create_logging_resource(payload: LoggingResourceCreate):
    """
    Queue creation of a new logging resource.
    
    The resource will be created asynchronously via a Celery task.
    """
    with LoggingResourceService() as svc:
        result = svc.create(
            name=payload.name,
            provider_type=payload.provider_type,
            account_id=payload.account_id,
            config=payload.config
        )
        
        if not result.success:
            raise HTTPException(status_code=400, detail=result.error)
        
        return result.data


@router.get(
    "/",
    response_model=LoggingResourceListResponse,
    dependencies=[Depends(require_scope("logging"))],
    summary="List all logging resources"
)
async def list_logging_resources():
    """Retrieve a list of all logging resources."""
    with LoggingResourceService() as svc:
        result = svc.list()
        
        return LoggingResourceListResponse(
            logging_resources=[LoggingResourceResponse.from_model(r) for r in result.items],
            total=result.total
        )


@router.get(
    "/{resource_id}",
    response_model=LoggingResourceResponse,
    dependencies=[Depends(require_scope("logging"))],
    summary="Get a specific logging resource"
)
async def get_logging_resource(resource_id: str):
    """Retrieve details for a specific logging resource."""
    with LoggingResourceService() as svc:
        result = svc.get(resource_id)
        
        if not result.success:
            raise HTTPException(status_code=404, detail=result.error)
        
        return LoggingResourceResponse.from_model(result.data)


@router.get(
    "/{account_id}/scan",
    dependencies=[Depends(require_scope("logging"))],
    summary="Scan existing CloudTrails/LogGroups"
)
async def scan_logging_resources(account_id: str):
    """Scan existing CloudTrails and LogGroups in an account."""
    with LoggingResourceService() as svc:
        result = svc.scan(account_id)
        
        if not result.success:
            raise HTTPException(status_code=400, detail=result.error)
        
        return result.data
