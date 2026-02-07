"""
Canary Service

Provides business logic for managing canary resources.
"""
from typing import Optional

from .base import BaseService, ServiceResult, ListResult
from src.models import CanaryResource, Account, TaskLog, TaskStatus


class CanaryService(BaseService):
    """
    Service for managing canary resources.
    
    Canaries are decoy credentials/resources used to detect unauthorized access.
    """
    
    def create(
        self,
        name: str,
        resource_type: str,
        account_id: str,
        logging_id: str,
        interval: int = 0,
        params: Optional[dict] = None
    ) -> ServiceResult[dict]:
        """
        Queue creation of a new canary resource.
        
        Canary creation is asynchronous via Celery task.
        
        Args:
            name: Display name for the canary
            resource_type: Type of canary (AWS_IAM_USER, AWS_BUCKET, GCP_SERVICE_ACCOUNT, GCP_BUCKET)
            account_id: UUID or name of the account (deployment target)
            logging_id: UUID of the logging resource
            interval: Rotation interval in seconds (0 for static)
            params: Optional module parameters
            
        Returns:
            ServiceResult containing task queued status
        """
        from src.tasks import create_canary as create_canary_task
        
        # Resolve account
        account = self._resolve_by_id_or_name(Account, account_id)
        if not account:
            return ServiceResult.fail(f"Account '{account_id}' not found")
        
        try:
            async_result = create_canary_task.delay(
                name=name,
                resource_type_str=resource_type,
                interval_seconds=interval,
                account_id_str=str(account.id),
                module_params=params,
                logging_resource_id_str=logging_id
            )
            log = TaskLog(
                celery_task_id=async_result.id,
                task_name="create_canary",
                source="user",
                status=TaskStatus.PENDING,
            )
            self.db.add(log)
            self.db.commit()
            return ServiceResult.ok({"status": "queued", "name": name, "task_id": async_result.id})
        except Exception as e:
            return ServiceResult.fail(f"Error queuing canary creation: {e}")
    
    def list(self) -> ListResult[CanaryResource]:
        """
        List all canary resources.
        
        Returns:
            ListResult containing all canaries
        """
        canaries = self.db.query(CanaryResource).all()
        return ListResult(items=canaries, total=len(canaries))
    
    def get(self, identifier: str) -> ServiceResult[CanaryResource]:
        """
        Get a specific canary by ID or name.
        
        Args:
            identifier: Canary UUID or name
            
        Returns:
            ServiceResult containing the CanaryResource or error
        """
        canary = self._resolve_by_id_or_name(CanaryResource, identifier)
        if not canary:
            return ServiceResult.fail(f"Canary '{identifier}' not found")
        return ServiceResult.ok(canary)
    
    def delete(self, identifier: str) -> ServiceResult[dict]:
        """
        Queue deletion of a canary resource.
        
        Canary deletion is asynchronous via Celery task.
        
        Args:
            identifier: Canary UUID or name
            
        Returns:
            ServiceResult containing task queued status or error
        """
        from src.tasks import delete_canary as delete_canary_task
        
        canary = self._resolve_by_id_or_name(CanaryResource, identifier)
        if not canary:
            return ServiceResult.fail(f"Canary '{identifier}' not found")
        
        try:
            async_result = delete_canary_task.delay(str(canary.id))
            log = TaskLog(
                celery_task_id=async_result.id,
                task_name="delete_canary",
                source="user",
                status=TaskStatus.PENDING,
                canary_id=canary.id,
            )
            self.db.add(log)
            self.db.commit()
            return ServiceResult.ok({
                "status": "queued",
                "id": str(canary.id),
                "name": canary.name,
                "task_id": async_result.id,
            })
        except Exception as e:
            return ServiceResult.fail(f"Error queuing canary deletion: {e}")
    
    def get_credentials(self, identifier: str) -> ServiceResult[dict]:
        """
        Get stored credentials for a canary.
        
        Args:
            identifier: Canary UUID or name
            
        Returns:
            ServiceResult containing credentials dictionary
        """
        canary = self._resolve_by_id_or_name(CanaryResource, identifier)
        if not canary:
            return ServiceResult.fail(f"Canary '{identifier}' not found")
        
        return ServiceResult.ok({
            "canary_id": str(canary.id),
            "canary_name": canary.name,
            "credentials": canary.canary_credentials
        })
    
    def trigger(self, identifier: str) -> ServiceResult[dict]:
        """
        Execute a trigger action to simulate canary access.
        
        Args:
            identifier: Canary UUID or name
            
        Returns:
            ServiceResult containing trigger result
        """
        from src.triggers import get_trigger
        
        canary = self._resolve_by_id_or_name(CanaryResource, identifier)
        if not canary:
            return ServiceResult.fail(f"Canary '{identifier}' not found")
        
        trigger = get_trigger(canary.resource_type)
        if not trigger:
            return ServiceResult.fail(
                f"No trigger implementation for type {canary.resource_type.value}"
            )
        
        try:
            success = trigger.execute(canary)
            return ServiceResult.ok({
                "success": success,
                "message": (
                    "Trigger executed. Events may take a few minutes to appear."
                    if success else "Trigger execution failed"
                )
            })
        except Exception as e:
            return ServiceResult.fail(f"Error executing trigger: {e}")
