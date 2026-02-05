"""Environment-related Pydantic schemas."""
from pydantic import BaseModel
from typing import Optional
from datetime import datetime


class EnvironmentCreate(BaseModel):
    """Request schema for creating an environment."""
    name: str
    provider: str  # AWS, GCP
    credentials: dict
    config: Optional[dict] = None


class EnvironmentResponse(BaseModel):
    """Response schema for environment data."""
    id: str
    name: str
    provider_type: str
    status: str
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class EnvironmentListResponse(BaseModel):
    """Response schema for list of environments."""
    environments: list[EnvironmentResponse]
    total: int


class SyncResult(BaseModel):
    """Response schema for sync operation."""
    created: list[str]
    updated: list[str]
    skipped: list[str]
    errors: list[dict]
