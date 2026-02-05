"""
Alerts API Routes

Provides endpoints for viewing and managing security alerts.
"""
from fastapi import APIRouter, Depends, Query
from typing import Optional

from ..auth import require_scope
from ..schemas.alert import AlertResponse, AlertListResponse
from ...cli.utils import get_db_session, resolve_canary, resolve_environment
from ...models import Alert, CanaryResource

router = APIRouter(prefix="/alerts")


@router.get(
    "/",
    response_model=AlertListResponse,
    dependencies=[Depends(require_scope("alerts"))],
    summary="List alerts"
)
async def list_alerts(
    canary: Optional[str] = Query(None, description="Filter by canary name or ID"),
    env: Optional[str] = Query(None, description="Filter by environment name or ID"),
    status: Optional[str] = Query(None, description="Filter by alert status")
):
    """
    Retrieve a list of security alerts.
    
    Optionally filter by canary, environment, or status.
    """
    db = get_db_session()
    try:
        query = db.query(Alert).join(CanaryResource)
        
        # Apply filters
        if canary:
            canary_obj = resolve_canary(db, canary)
            if canary_obj:
                query = query.filter(Alert.canary_id == canary_obj.id)
            else:
                # Return empty if canary not found
                return AlertListResponse(alerts=[], total=0)
        
        if env:
            env_obj = resolve_environment(db, env)
            if env_obj:
                query = query.filter(CanaryResource.environment_id == env_obj.id)
            else:
                return AlertListResponse(alerts=[], total=0)
        
        if status:
            query = query.filter(Alert.status == status)
        
        alerts = query.order_by(Alert.created_at.desc()).all()
        
        return AlertListResponse(
            alerts=[
                AlertResponse(
                    id=str(a.id),
                    canary_id=str(a.canary_id),
                    canary_name=a.canary.name if a.canary else None,
                    external_id=a.external_id,
                    event_type=a.event_type,
                    source_ip=a.source_ip,
                    status=a.status.value,
                    created_at=a.created_at
                )
                for a in alerts
            ],
            total=len(alerts)
        )
    finally:
        db.close()


@router.get(
    "/{alert_id}",
    response_model=AlertResponse,
    dependencies=[Depends(require_scope("alerts"))],
    summary="Get a specific alert"
)
async def get_alert(alert_id: str):
    """Retrieve details for a specific alert."""
    db = get_db_session()
    try:
        import uuid
        from fastapi import HTTPException
        
        try:
            alert = db.query(Alert).filter(
                Alert.id == uuid.UUID(alert_id)
            ).first()
        except ValueError:
            # Try by external_id
            alert = db.query(Alert).filter(
                Alert.external_id == alert_id
            ).first()
        
        if not alert:
            raise HTTPException(status_code=404, detail=f"Alert '{alert_id}' not found")
        
        return AlertResponse(
            id=str(alert.id),
            canary_id=str(alert.canary_id),
            canary_name=alert.canary.name if alert.canary else None,
            external_id=alert.external_id,
            event_type=alert.event_type,
            source_ip=alert.source_ip,
            status=alert.status.value,
            created_at=alert.created_at
        )
    finally:
        db.close()
