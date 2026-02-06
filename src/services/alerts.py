"""
Alert Service

Provides business logic for viewing security alerts.
"""
import uuid as uuid_module
from typing import Optional

from .base import BaseService, ServiceResult, ListResult
from src.models import Alert, CanaryResource, Account


class AlertService(BaseService):
    """
    Service for viewing security alerts.
    
    Alerts are generated when canary credentials are accessed.
    """
    
    def list(
        self,
        canary: Optional[str] = None,
        account: Optional[str] = None,
        status: Optional[str] = None
    ) -> ListResult[Alert]:
        """
        List alerts with optional filtering.
        
        Args:
            canary: Filter by canary name or ID
            account: Filter by account name or ID
            status: Filter by alert status
            
        Returns:
            ListResult containing matching alerts
        """
        query = self.db.query(Alert).join(CanaryResource)
        
        if canary:
            canary_obj = self._resolve_by_id_or_name(CanaryResource, canary)
            if canary_obj:
                query = query.filter(Alert.canary_id == canary_obj.id)
            else:
                return ListResult(items=[], total=0)
        
        if account:
            account_obj = self._resolve_by_id_or_name(Account, account)
            if account_obj:
                query = query.filter(CanaryResource.account_id == account_obj.id)
            else:
                return ListResult(items=[], total=0)
        
        if status:
            query = query.filter(Alert.status == status)
        
        alerts = query.order_by(Alert.created_at.desc()).all()
        return ListResult(items=alerts, total=len(alerts))
    
    def get(self, identifier: str) -> ServiceResult[Alert]:
        """
        Get a specific alert by ID or external ID.
        
        Args:
            identifier: Alert UUID or external ID
            
        Returns:
            ServiceResult containing the Alert or error
        """
        # Try UUID first
        try:
            alert = self.db.query(Alert).filter(
                Alert.id == uuid_module.UUID(identifier)
            ).first()
            if alert:
                return ServiceResult.ok(alert)
        except ValueError:
            pass
        
        # Try external_id
        alert = self.db.query(Alert).filter(
            Alert.external_id == identifier
        ).first()
        
        if not alert:
            return ServiceResult.fail(f"Alert '{identifier}' not found")
        return ServiceResult.ok(alert)
