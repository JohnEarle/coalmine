"""Logging resource-related Pydantic schemas."""
from pydantic import BaseModel
from typing import Optional
from datetime import datetime


class LoggingResourceCreate(BaseModel):
    """Request schema for creating a logging resource."""
    name: str
    provider_type: str  # AWS_CLOUDTRAIL, GCP_AUDIT_SINK, etc.
    environment_id: str
    config: Optional[dict] = None


class LoggingResourceResponse(BaseModel):
    """Response schema for logging resource data."""
    id: str
    name: str
    provider_type: str
    environment_id: str
    status: str
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class LoggingResourceListResponse(BaseModel):
    """Response schema for list of logging resources."""
    logging_resources: list[LoggingResourceResponse]
    total: int
