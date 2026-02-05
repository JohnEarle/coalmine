"""
Environment Management API Routes

Provides endpoints for managing cloud environments.
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from typing import Optional

from ..auth import require_permission, require_scope
from ..schemas.environment import (
    EnvironmentCreate, EnvironmentResponse, EnvironmentListResponse, SyncResult
)
from ...cli.utils import resolve_environment, get_db_session
from ...models import CloudEnvironment
from ...environment_sync import sync_environments_from_yaml

router = APIRouter(prefix="/environments")


@router.post(
    "/",
    response_model=EnvironmentResponse,
    dependencies=[
        Depends(require_permission("write")),
        Depends(require_scope("environments"))
    ],
    summary="Create a new environment"
)
async def create_environment(payload: EnvironmentCreate):
    """Create a new cloud environment."""
    db = get_db_session()
    try:
        # Check for existing
        existing = db.query(CloudEnvironment).filter(
            CloudEnvironment.name == payload.name
        ).first()
        if existing:
            raise HTTPException(
                status_code=409,
                detail=f"Environment '{payload.name}' already exists"
            )
        
        env = CloudEnvironment(
            name=payload.name,
            provider_type=payload.provider,
            credentials=payload.credentials,
            config=payload.config or {}
        )
        db.add(env)
        db.commit()
        db.refresh(env)
        
        return EnvironmentResponse(
            id=str(env.id),
            name=env.name,
            provider_type=env.provider_type,
            status=env.status.value,
            created_at=env.created_at
        )
    finally:
        db.close()


@router.get(
    "/",
    response_model=EnvironmentListResponse,
    dependencies=[Depends(require_scope("environments"))],
    summary="List all environments"
)
async def list_environments():
    """Retrieve a list of all cloud environments."""
    db = get_db_session()
    try:
        environments = db.query(CloudEnvironment).all()
        return EnvironmentListResponse(
            environments=[
                EnvironmentResponse(
                    id=str(e.id),
                    name=e.name,
                    provider_type=e.provider_type,
                    status=e.status.value,
                    created_at=e.created_at
                )
                for e in environments
            ],
            total=len(environments)
        )
    finally:
        db.close()


@router.get(
    "/{env_id}",
    response_model=EnvironmentResponse,
    dependencies=[Depends(require_scope("environments"))],
    summary="Get a specific environment"
)
async def get_environment(env_id: str):
    """Retrieve details for a specific environment by ID or name."""
    db = get_db_session()
    try:
        env = resolve_environment(db, env_id)
        if not env:
            raise HTTPException(status_code=404, detail=f"Environment '{env_id}' not found")
        
        return EnvironmentResponse(
            id=str(env.id),
            name=env.name,
            provider_type=env.provider_type,
            status=env.status.value,
            created_at=env.created_at
        )
    finally:
        db.close()


@router.post(
    "/sync",
    response_model=SyncResult,
    dependencies=[
        Depends(require_permission("write")),
        Depends(require_scope("environments"))
    ],
    summary="Sync environments from YAML config"
)
async def sync_environments(
    dry_run: bool = Query(False, description="Preview changes without applying"),
    force: bool = Query(False, description="Overwrite existing DB entries")
):
    """
    Synchronize environments from config/environments.yaml to the database.
    
    By default, database entries take precedence over YAML.
    Use force=true to overwrite existing entries.
    """
    result = sync_environments_from_yaml(dry_run=dry_run, force=force)
    return SyncResult(**result)
