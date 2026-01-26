from typing import Dict, Any
from .base import ResourceManager
from ..logging_utils import _update_gcp_sink_filter
from ..models import LoggingProviderType, ResourceType

class GcpServiceAccountHandler(ResourceManager):
    def get_tform_vars(self, physical_id: str, env_config: Dict[str, Any], module_params: Dict[str, Any]) -> Dict[str, Any]:
        vars_dict = {"service_account_id": physical_id}
        
        # Project ID resolution logic
        project_id = env_config.get("project_id")
        # Check credentials if config doesn't have it? env_config passed here is usually just env_obj.config
        # But in canary.py, it checks credentials too.
        # I'll update the signature of get_tform_vars to take env_obj or just pass the full config + creds merged?
        # The base class defines (physical_id, env_config, module_params).
        # I should probably pass env_obj or a merged dict.
        
        if project_id:
             vars_dict["project_id"] = project_id

        if module_params:
            vars_dict.update(module_params)
        return vars_dict
        
    def enable_logging(self, resource_val: str, log_resource: Any, env_obj: Any) -> None:
        if "GCP" in log_resource.provider_type.value: # Handles GCP_AUDIT_LOG/SINK
             sink_name = log_resource.configuration.get("sink_name")
             # Fallback to Tofu Output if sink_name not in config (handled in canary.py currently)
             # But here use what's available.
             
             if not sink_name and log_resource.configuration.get("tofu_output"):
                 out = log_resource.configuration["tofu_output"]
                 if "sink_name" in out:
                     sink_name = out["sink_name"]["value"]
                     
             if sink_name:
                 _update_gcp_sink_filter(env_obj, sink_name, resource_val, ResourceType.GCP_SERVICE_ACCOUNT, add=True)

    def disable_logging(self, resource_val: str, log_resource: Any, env_obj: Any) -> None:
        if "GCP" in log_resource.provider_type.value:
             sink_name = log_resource.configuration.get("sink_name")
             if not sink_name and log_resource.configuration.get("tofu_output"):
                 out = log_resource.configuration["tofu_output"]
                 if "sink_name" in out:
                     sink_name = out["sink_name"]["value"]

             if sink_name:
                 _update_gcp_sink_filter(env_obj, sink_name, resource_val, ResourceType.GCP_SERVICE_ACCOUNT, add=False)
