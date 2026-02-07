from typing import Dict, Any, Optional
from .base import ResourceManager
from ..logging_utils import _apply_logging_with_canaries
from ..models import LoggingProviderType, ResourceType

class GcpBucketHandler(ResourceManager):
    def get_tform_vars(self, physical_id: str, env_config: Dict[str, Any], module_params: Dict[str, Any]) -> Dict[str, Any]:
        vars_dict = {"bucket_name": physical_id}
        
        project_id = env_config.get("project_id")
        if project_id:
             vars_dict["project"] = project_id  # Template expects 'project'
             
        if module_params:
            vars_dict.update(module_params)
        return vars_dict
        
    def enable_logging(self, resource_val: str, log_resource: Any, env_obj: Any) -> None:
        """Update logging resource filter to include this canary via Terraform."""
        if log_resource and "GCP" in log_resource.provider_type.value:
            _apply_logging_with_canaries(log_resource)

    def disable_logging(self, resource_val: str, log_resource: Any, env_obj: Any) -> None:
        """Update logging resource filter removing this canary via Terraform."""
        if log_resource and "GCP" in log_resource.provider_type.value:
            _apply_logging_with_canaries(log_resource)

    def validate(self, account: Any, module_params: Optional[Dict[str, Any]] = None, logging_resource: Optional[Any] = None) -> None:
        if not account or not account.credential or account.credential.provider != "GCP":
            raise ValueError("Account provider mismatch: Expected GCP")
