import os
import datetime
import uuid
from contextlib import contextmanager
from typing import Optional, Dict, Any, Tuple

from ..models import (
    SessionLocal, ResourceHistory, ResourceStatus, ActionType, 
    CanaryResource, LoggingResource
)
from ..tofu_manager import TofuManager
from ..logging_config import get_logger
from .helpers import (
    TOFU_BASE_DIR, STATE_BASE_DIR, _get_template_name, _get_backend_config
)

logger = get_logger(__name__)

class ResourceLifecycleManager:
    """
    Context manager for handling resource lifecycle transactions.
    
    Provides ACID transaction management, error handling, and compensating transactions
    (resource cleanup) for Coalmine resources.
    """
    
    def __init__(self, resource_id: str = None, action_type: ActionType = ActionType.CREATE):
        self.resource_id = resource_id
        self.action_type = action_type
        self.db = None
        self.resource = None
        self.manager = None
        self.vars_dict = {}
        self.exec_env = {}
        self.cloud_resource_created = False
        self.should_cleanup = False
        self.template_path = None
        self.work_dir = None

    def __enter__(self):
        self.db = SessionLocal()
        if self.resource_id:
            # Try finding in both tables (polymorphic lookup would be better but keeping simple)
            try:
                u_id = uuid.UUID(self.resource_id)
                self.resource = self.db.query(CanaryResource).filter(CanaryResource.id == u_id).first()
                if not self.resource:
                    self.resource = self.db.query(LoggingResource).filter(LoggingResource.id == u_id).first()
            except ValueError:
                pass # Invalid UUID
                
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        try:
            if exc_type:
                logger.error(f"Error in transaction for resource {self.resource_id}: {exc_val}")
                self.db.rollback()
                self._handle_failure(exc_val)
            else:
                self.db.commit()
                if self.resource:
                    logger.info(f"Transaction successful for {self.resource.name}")
        finally:
            self.db.close()
            
    def init_tofu(self, template_name: str, env_vars: Dict[str, str]):
        """Initialize TofuManager."""
        if not self.resource:
             raise ValueError("Resource must be set before initializing Tofu")
             
        self.template_path = os.path.join(TOFU_BASE_DIR, template_name)
        self.work_dir = os.path.join(STATE_BASE_DIR, str(self.resource.id))
        self.resource.tf_state_path = self.work_dir
        
        self.manager = TofuManager(self.template_path, self.work_dir)
        self.exec_env = env_vars
        
        backend_config = _get_backend_config(str(self.resource.id))
        self.manager.init(env=self.exec_env, backend_config=backend_config, clean_env=True)

    def apply(self, vars_dict: Dict[str, Any]):
        """Run Tofu Apply."""
        if not self.manager:
            raise ValueError("TofuManager not initialized")
            
        self.vars_dict = vars_dict
        output = self.manager.apply(vars_dict, env=self.exec_env, clean_env=True)
        self.cloud_resource_created = True # Mark for cleanup if needed
        return output

    def destroy(self, vars_dict: Dict[str, Any]):
        """Run Tofu Destroy."""
        if not self.manager:
             raise ValueError("TofuManager not initialized")
        
        self.vars_dict = vars_dict
        return self.manager.destroy(vars_dict, env=self.exec_env, clean_env=True)

    def verify_plan(self):
        """Run Tofu Plan for verification."""
        if not self.manager:
             return
             
        plan_code, _ = self.manager.plan(self.vars_dict, env=self.exec_env, detailed_exitcode=True, clean_env=True)
        if plan_code != 0:
             raise Exception(f"Verification Failed. Tofu Plan ExitCode: {plan_code}")

    def _handle_failure(self, exception):
        """Handle failure: Cleanup and Record Error."""
        # Compensating Transaction: Cleanup cloud resource if created
        if self.cloud_resource_created and self.manager and self.action_type == ActionType.CREATE:
            try:
                logger.info(f"Attempting cleanup of cloud resource for {self.resource_id}...")
                self.manager.destroy(self.vars_dict, env=self.exec_env, clean_env=True)
                logger.info(f"Cleanup successful for {self.resource_id}")
            except Exception as cleanup_err:
                logger.error(f"Cleanup FAILED for {self.resource_id}: {cleanup_err}")

        # Record error in new transaction
        if self.resource:
            try:
                # Use a fresh session for error recording
                db_err = SessionLocal()
                err_res = None
                
                # Check type again to query correct table
                if isinstance(self.resource, CanaryResource):
                     err_res = db_err.query(CanaryResource).filter(CanaryResource.id == self.resource.id).first()
                elif isinstance(self.resource, LoggingResource):
                     err_res = db_err.query(LoggingResource).filter(LoggingResource.id == self.resource.id).first()

                if err_res:
                    err_res.status = ResourceStatus.ERROR
                    
                    history = ResourceHistory(
                        resource_id=err_res.id,
                        action=self.action_type,
                        details={"error": str(exception), "cleanup_attempted": self.cloud_resource_created}
                    )
                    db_err.add(history)
                    db_err.commit()
                db_err.close()
            except Exception as record_err:
                logger.error(f"Failed to record error state: {record_err}")
