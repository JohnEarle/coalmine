"""
Canary Management API Routes

Provides endpoints for creating, listing, deleting canaries and managing credentials.
"""
from fastapi import APIRouter, Depends, HTTPException
from typing import List

from ..auth import require_permission, require_scope, get_current_key
from ..schemas.canary import (
    CanaryCreate, CanaryResponse, CanaryListResponse, 
    CredentialsResponse, TriggerResponse
)
from ...cli.utils import resolve_canary, get_db_session
from ...models import CanaryResource
from ...tasks import create_canary as create_canary_task, delete_canary as delete_canary_task
from ...triggers import get_trigger

router = APIRouter(prefix="/canaries")


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
    create_canary_task.delay(
        name=payload.name,
        resource_type_str=payload.resource_type,
        interval_seconds=payload.interval,
        environment_id_str=payload.environment_id,
        module_params=payload.params,
        logging_resource_id_str=payload.logging_id
    )
    return {"status": "queued", "name": payload.name}


@router.get(
    "/",
    response_model=CanaryListResponse,
    dependencies=[Depends(require_scope("canaries"))],
    summary="List all canaries"
)
async def list_canaries():
    """Retrieve a list of all canary resources."""
    db = get_db_session()
    try:
        canaries = db.query(CanaryResource).all()
        return CanaryListResponse(
            canaries=[
                CanaryResponse(
                    id=str(c.id),
                    name=c.name,
                    resource_type=c.resource_type.value,
                    status=c.status.value,
                    current_resource_id=c.current_resource_id,
                    expires_at=c.expires_at,
                    created_at=c.created_at
                )
                for c in canaries
            ],
            total=len(canaries)
        )
    finally:
        db.close()


@router.get(
    "/{canary_id}",
    response_model=CanaryResponse,
    dependencies=[Depends(require_scope("canaries"))],
    summary="Get a specific canary"
)
async def get_canary(canary_id: str):
    """Retrieve details for a specific canary by ID or name."""
    db = get_db_session()
    try:
        canary = resolve_canary(db, canary_id)
        if not canary:
            raise HTTPException(status_code=404, detail=f"Canary '{canary_id}' not found")
        
        return CanaryResponse(
            id=str(canary.id),
            name=canary.name,
            resource_type=canary.resource_type.value,
            status=canary.status.value,
            current_resource_id=canary.current_resource_id,
            expires_at=canary.expires_at,
            created_at=canary.created_at
        )
    finally:
        db.close()


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
    db = get_db_session()
    try:
        canary = resolve_canary(db, canary_id)
        if not canary:
            raise HTTPException(status_code=404, detail=f"Canary '{canary_id}' not found")
        
        delete_canary_task.delay(str(canary.id))
        return {"status": "queued", "id": str(canary.id), "name": canary.name}
    finally:
        db.close()


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
    db = get_db_session()
    try:
        canary = resolve_canary(db, canary_id)
        if not canary:
            raise HTTPException(status_code=404, detail=f"Canary '{canary_id}' not found")
        
        return CredentialsResponse(
            canary_id=str(canary.id),
            canary_name=canary.name,
            credentials=canary.canary_credentials
        )
    finally:
        db.close()


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
    db = get_db_session()
    try:
        canary = resolve_canary(db, canary_id)
        if not canary:
            raise HTTPException(status_code=404, detail=f"Canary '{canary_id}' not found")
        
        trigger = get_trigger(canary.resource_type)
        if not trigger:
            raise HTTPException(
                status_code=501,
                detail=f"No trigger implementation for type {canary.resource_type.value}"
            )
        
        success = trigger.execute(canary)
        return TriggerResponse(
            success=success,
            message="Trigger executed. Events may take a few minutes to appear." if success else "Trigger execution failed"
        )
    finally:
        db.close()
