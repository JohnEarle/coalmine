from typing import Dict, Any, Optional
from .base import ResourceManager
from ..logging_utils import _apply_logging_with_canaries
from ..models import LoggingProviderType

class AwsBucketHandler(ResourceManager):
    def get_tform_vars(self, physical_id: str, env_config: Dict[str, Any], module_params: Dict[str, Any]) -> Dict[str, Any]:
        vars_dict = {"bucket_name": physical_id}
        if module_params:
            vars_dict.update(module_params)
        # Use credential region as fallback if not specified in params
        if "region" not in vars_dict and env_config.get("aws_region"):
            vars_dict["region"] = env_config["aws_region"]
        return vars_dict
        
    def enable_logging(self, resource_val: str, log_resource: Any, env_obj: Any) -> None:
        """Update logging resource filter to include this canary via Terraform."""
        if log_resource and log_resource.provider_type == LoggingProviderType.AWS_CLOUDTRAIL:
            _apply_logging_with_canaries(log_resource)

    def disable_logging(self, resource_val: str, log_resource: Any, env_obj: Any) -> None:
        """Update logging resource filter removing this canary via Terraform."""
        if log_resource and log_resource.provider_type == LoggingProviderType.AWS_CLOUDTRAIL:
            _apply_logging_with_canaries(log_resource)

    def validate(self, account: Any, module_params: Optional[Dict[str, Any]] = None, logging_resource: Optional[Any] = None) -> None:
        if not account or not account.credential or account.credential.provider != "AWS":
            raise ValueError("Account provider mismatch: Expected AWS")

        if not logging_resource:
             raise ValueError("AWS_BUCKET requires a valid logging_resource_id.")
