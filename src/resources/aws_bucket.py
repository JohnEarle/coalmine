from typing import Dict, Any
from .base import ResourceManager
from ..logging_utils import _update_trail_selectors
from ..models import LoggingProviderType

class AwsBucketHandler(ResourceManager):
    def get_tform_vars(self, physical_id: str, env_config: Dict[str, Any], module_params: Dict[str, Any]) -> Dict[str, Any]:
        vars_dict = {"bucket_name": physical_id}
        if module_params:
            vars_dict.update(module_params)
        return vars_dict
        
    def enable_logging(self, resource_val: str, log_resource: Any, env_obj: Any) -> None:
        if log_resource.provider_type == LoggingProviderType.AWS_CLOUDTRAIL:
             trail_name = log_resource.configuration.get("trail_name") or log_resource.name
             bucket_arn = f"arn:aws:s3:::{resource_val}"
             _update_trail_selectors(env_obj, trail_name, bucket_arn, add=True)

    def disable_logging(self, resource_val: str, log_resource: Any, env_obj: Any) -> None:
        if log_resource.provider_type == LoggingProviderType.AWS_CLOUDTRAIL:
             trail_name = log_resource.configuration.get("trail_name") or log_resource.name
             bucket_arn = f"arn:aws:s3:::{resource_val}"
             _update_trail_selectors(env_obj, trail_name, bucket_arn, add=False)
