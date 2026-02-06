"""
Alerts API Routes

Provides endpoints for viewing and managing security alerts.
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime

from ..auth import require_scope
from src.services import AlertService

router = APIRouter(prefix="/alerts")


# =============================================================================
# Schemas
# =============================================================================

class AlertResponse(BaseModel):
    """Response schema for alert data."""
    id: str
    canary_id: str
    canary_name: Optional[str] = None
    account_name: Optional[str] = None
    external_id: Optional[str] = None
    event_name: Optional[str] = None
    source_ip: Optional[str] = None
    user_agent: Optional[str] = None
    timestamp: Optional[datetime] = None
    status: str
    created_at: Optional[datetime] = None

    @classmethod
    def from_model(cls, alert):
        """Create response from Alert model."""
        account_name = None
        if alert.canary and alert.canary.account:
            account_name = alert.canary.account.name
        
        return cls(
            id=str(alert.id),
            canary_id=str(alert.canary_id),
            canary_name=alert.canary.name if alert.canary else None,
            account_name=account_name,
            external_id=alert.external_id,
            event_name=alert.event_name,
            source_ip=alert.source_ip,
            user_agent=alert.user_agent,
            timestamp=alert.timestamp,
            status=alert.status.value if alert.status else "UNKNOWN",
            created_at=alert.created_at
        )


class AlertListResponse(BaseModel):
    """Response schema for list of alerts."""
    alerts: List[AlertResponse]
    total: int


# =============================================================================
# Endpoints
# =============================================================================

@router.get(
    "/",
    response_model=AlertListResponse,
    dependencies=[Depends(require_scope("alerts"))],
    summary="List alerts"
)
async def list_alerts(
    canary: Optional[str] = Query(None, description="Filter by canary name or ID"),
    account: Optional[str] = Query(None, description="Filter by account name or ID"),
    status: Optional[str] = Query(None, description="Filter by alert status")
):
    """
    Retrieve a list of security alerts.
    
    Optionally filter by canary, account, or status.
    """
    with AlertService() as svc:
        result = svc.list(canary=canary, account=account, status=status)
        
        return AlertListResponse(
            alerts=[AlertResponse.from_model(a) for a in result.items],
            total=result.total
        )


@router.get(
    "/{alert_id}",
    response_model=AlertResponse,
    dependencies=[Depends(require_scope("alerts"))],
    summary="Get a specific alert"
)
async def get_alert(alert_id: str):
    """Retrieve details for a specific alert."""
    with AlertService() as svc:
        result = svc.get(alert_id)
        
        if not result.success:
            raise HTTPException(status_code=404, detail=result.error)
        
        return AlertResponse.from_model(result.data)
