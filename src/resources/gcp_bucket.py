from typing import Dict, Any
from .base import ResourceManager
from ..logging_utils import _update_gcp_sink_filter
from ..models import LoggingProviderType, ResourceType

class GcpBucketHandler(ResourceManager):
    def get_tform_vars(self, physical_id: str, env_config: Dict[str, Any], module_params: Dict[str, Any]) -> Dict[str, Any]:
        vars_dict = {"bucket_name": physical_id}
        
        project_id = env_config.get("project_id")
        if project_id:
             vars_dict["project_id"] = project_id
             
        if module_params:
            vars_dict.update(module_params)
        return vars_dict
        
    def enable_logging(self, resource_val: str, log_resource: Any, env_obj: Any) -> None:
         if "GCP" in log_resource.provider_type.value:
             sink_name = log_resource.configuration.get("sink_name")
             if not sink_name and log_resource.configuration.get("tofu_output"):
                 out = log_resource.configuration["tofu_output"]
                 if "sink_name" in out:
                     sink_name = out["sink_name"]["value"]
                     
             if sink_name:
                 _update_gcp_sink_filter(env_obj, sink_name, resource_val, ResourceType.GCP_BUCKET, add=True)

    def disable_logging(self, resource_val: str, log_resource: Any, env_obj: Any) -> None:
         if "GCP" in log_resource.provider_type.value:
             sink_name = log_resource.configuration.get("sink_name")
             if not sink_name and log_resource.configuration.get("tofu_output"):
                 out = log_resource.configuration["tofu_output"]
                 if "sink_name" in out:
                     sink_name = out["sink_name"]["value"]

             if sink_name:
                 _update_gcp_sink_filter(env_obj, sink_name, resource_val, ResourceType.GCP_BUCKET, add=False)
