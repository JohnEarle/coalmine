"""
Logging Resource Management API Routes

Provides endpoints for managing logging resources (CloudTrail, GCP Audit Sink, etc.)
"""
from fastapi import APIRouter, Depends, HTTPException

from ..auth import require_permission, require_scope
from ..schemas.logging import (
    LoggingResourceCreate, LoggingResourceResponse, LoggingResourceListResponse
)
from ...cli.utils import get_db_session, resolve_environment
from ...models import LoggingResource, LoggingProviderType
from ...tasks import create_logging_resource as create_logging_task

router = APIRouter(prefix="/logging-resources")


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
    # Validate provider type
    try:
        provider = LoggingProviderType(payload.provider_type)
    except ValueError:
        valid_types = [t.value for t in LoggingProviderType]
        raise HTTPException(
            status_code=400,
            detail=f"Invalid provider_type. Valid types: {valid_types}"
        )
    
    # Validate environment exists
    db = get_db_session()
    try:
        env = resolve_environment(db, payload.environment_id)
        if not env:
            raise HTTPException(
                status_code=404,
                detail=f"Environment '{payload.environment_id}' not found"
            )
        env_id_str = str(env.id)
    finally:
        db.close()
    
    create_logging_task.delay(
        name=payload.name,
        provider_type_str=payload.provider_type,
        environment_id_str=env_id_str,
        configuration=payload.config
    )
    return {"status": "queued", "name": payload.name}


@router.get(
    "/",
    response_model=LoggingResourceListResponse,
    dependencies=[Depends(require_scope("logging"))],
    summary="List all logging resources"
)
async def list_logging_resources():
    """Retrieve a list of all logging resources."""
    db = get_db_session()
    try:
        resources = db.query(LoggingResource).all()
        return LoggingResourceListResponse(
            logging_resources=[
                LoggingResourceResponse(
                    id=str(r.id),
                    name=r.name,
                    provider_type=r.provider_type.value,
                    environment_id=str(r.environment_id),
                    status=r.status.value,
                    created_at=r.created_at
                )
                for r in resources
            ],
            total=len(resources)
        )
    finally:
        db.close()


@router.get(
    "/{resource_id}",
    response_model=LoggingResourceResponse,
    dependencies=[Depends(require_scope("logging"))],
    summary="Get a specific logging resource"
)
async def get_logging_resource(resource_id: str):
    """Retrieve details for a specific logging resource."""
    db = get_db_session()
    try:
        import uuid
        try:
            resource = db.query(LoggingResource).filter(
                LoggingResource.id == uuid.UUID(resource_id)
            ).first()
        except ValueError:
            # Try by name
            resource = db.query(LoggingResource).filter(
                LoggingResource.name == resource_id
            ).first()
        
        if not resource:
            raise HTTPException(status_code=404, detail=f"Logging resource '{resource_id}' not found")
        
        return LoggingResourceResponse(
            id=str(resource.id),
            name=resource.name,
            provider_type=resource.provider_type.value,
            environment_id=str(resource.environment_id),
            status=resource.status.value,
            created_at=resource.created_at
        )
    finally:
        db.close()
