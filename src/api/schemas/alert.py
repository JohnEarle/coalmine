"""Alert-related Pydantic schemas."""
from pydantic import BaseModel
from typing import Optional
from datetime import datetime


class AlertResponse(BaseModel):
    """Response schema for alert data."""
    id: str
    canary_id: str
    canary_name: Optional[str] = None
    external_id: str
    event_type: str
    source_ip: Optional[str] = None
    status: str
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class AlertListResponse(BaseModel):
    """Response schema for list of alerts."""
    alerts: list[AlertResponse]
    total: int
