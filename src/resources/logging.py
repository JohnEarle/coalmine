from typing import Dict, Any
from .base import ResourceManager
from ..models import LoggingResource, Account
from ..logging_utils import _update_trail_selectors, _update_gcp_sink_filter

class AwsCloudTrailHandler(ResourceManager):
    def get_tform_vars(self, physical_id: str, env_config: Dict[str, Any], module_params: Dict[str, Any]) -> Dict[str, Any]:
        vars_dict = {"name": physical_id}
        
        allowed_vars = ['region', 'tags', 'resource_prefix']
        if module_params:
            for key in allowed_vars:
                if key in module_params:
                    vars_dict[key] = module_params[key]
        
        # Merge global config if present and not overridden
        for key in allowed_vars:
             if key in env_config and key not in vars_dict:
                 vars_dict[key] = env_config[key]
                 
        return vars_dict

    def enable_logging(self, resource_val: str, log_resource: LoggingResource, account: Account) -> None:
        # No-op: logging resources do not log themselves
        pass

    def disable_logging(self, resource_val: str, log_resource: LoggingResource, account: Account) -> None:
        pass


class GcpAuditSinkHandler(ResourceManager):
    def get_tform_vars(self, physical_id: str, env_config: Dict[str, Any], module_params: Dict[str, Any]) -> Dict[str, Any]:
        vars_dict = {"name": physical_id}
        
        # Project ID Handling
        if "project_id" in module_params:
             vars_dict["project_id"] = module_params["project_id"]
        elif "project_id" in env_config:
             vars_dict["project_id"] = env_config["project_id"]
             
        if "project_id" not in vars_dict:
             raise ValueError("project_id must be provided in env config or module params for GCP_AUDIT_SINK")
             
        return vars_dict

    def enable_logging(self, resource_val: str, log_resource: LoggingResource, account: Account) -> None:
        pass

    def disable_logging(self, resource_val: str, log_resource: LoggingResource, account: Account) -> None:
        pass

