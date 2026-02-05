"""Canary-related Pydantic schemas."""
from pydantic import BaseModel
from typing import Optional, Any
from datetime import datetime


class CanaryCreate(BaseModel):
    """Request schema for creating a canary."""
    name: str
    resource_type: str
    environment_id: str
    logging_id: str
    interval: int = 0
    params: Optional[dict] = None


class CanaryResponse(BaseModel):
    """Response schema for canary data."""
    id: str
    name: str
    resource_type: str
    status: str
    current_resource_id: Optional[str] = None
    expires_at: Optional[datetime] = None
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class CanaryListResponse(BaseModel):
    """Response schema for list of canaries."""
    canaries: list[CanaryResponse]
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
